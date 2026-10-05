# -*- coding: utf-8 -*-
"""TASK-013 SecretRef / Keychain 密钥引用（60-04）测试。

覆盖：
1. GET /admin/secrets 无 token 401（后端鉴权）
2. POST upsert + GET 脱敏视图（不回明文）
3. 幂等 upsert（同 ref_key 覆盖，不产生重复行）
4. DELETE 幂等 + 审计
5. migrate 从 .env 迁移（幂等，不回明文）
6. resolve_llm_key：Keychain 优先，.env 兜底
7. PII/Retention/Region 标注字段落库可读

运行：backend/venv/Scripts/python.exe tests/test_secret_ref.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.models  # noqa: F401
import app.models_ai  # noqa: F401
import app.models_ontology  # noqa: F401
from fastapi.testclient import TestClient

from app.main import app
from app.db import SessionLocal
from app.models_ai import SecretEntry
from app.store_secrets import (mask_secret, set_secret, get_secret,
                               resolve_llm_key, migrate_env_to_keychain)

PASS, FAIL = [], []


def check(name: str, cond: bool, extra: str = ""):
    (PASS if cond else FAIL).append(name)
    print(f"{'  PASS' if cond else '  FAIL'}  {name}" + (f"  <{extra}>" if extra and not cond else ""))


def _unpack(r) -> dict:
    j = r.json()
    if isinstance(j, dict) and "data" in j and "code" in j:
        return j["data"]
    return j


def _bearer(c) -> dict:
    r = c.post("/api/auth/login", json={"username": "admin", "password": "123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['token']}"}


def main():
    with TestClient(app) as c:
        HA = _bearer(c)

        # 动态租户：SQLite 种子 admin.company_id=1；PG 种子可能不同（如 3）
        db0 = SessionLocal()
        try:
            from app.models import User
            CID = db0.query(User.company_id).filter(User.username == "admin").scalar() or 1
        finally:
            db0.close()
        print(f"[test] admin company_id={CID}")

        # 1. 无 token 被拒
        check("无 token GET /admin/secrets 401", c.get("/api/admin/secrets").status_code == 401)
        check("无 token POST /admin/secrets 401",
              c.post("/api/admin/secrets", json={"ref_key": "llm:deepseek", "value": "sk-x"}).status_code == 401)
        check("无 token DELETE 401", c.delete("/api/admin/secrets/llm:deepseek").status_code == 401)

        # 2. 写一条密钥（PII/Retention/Region 标注）
        r = c.post("/api/admin/secrets", headers=HA, json={
            "ref_key": "webhook:alert", "value": "sk-secret-alert-123456",
            "kind": "webhook", "pii_level": "high", "retention_days": 180, "region": "cn",
            "note": "核电站报警 webhook",
        })
        check("POST upsert 200", r.status_code == 200, r.text)
        body = _unpack(r)
        check("upsert ref_key", body.get("ok") is True and body.get("ref_key") == "webhook:alert")
        check("标注字段落库", body.get("pii_level") == "high" and body.get("retention_days") == 180
              and body.get("region") == "cn")
        check("响应不回明文", "sk-secret-alert-123456" not in r.text)

        # 3. GET 脱敏视图
        r = c.get("/api/admin/secrets", headers=HA)
        check("GET secrets 200", r.status_code == 200, r.text)
        body = _unpack(r)
        item = next((i for i in body.get("items", []) if i["ref_key"] == "webhook:alert"), None)
        check("列表含 ref_key", item is not None)
        check("has_value=True", item is not None and item["has_value"] is True)
        check("列表不回明文", "sk-secret-alert-123456" not in r.text)
        check("masked 含掩码", item is not None and "****" in item["masked"])

        # 4. 幂等 upsert：同 ref_key 覆盖，行数不变
        db = SessionLocal()
        try:
            before = db.query(SecretEntry).filter(
                SecretEntry.company_id == CID, SecretEntry.ref_key == "webhook:alert").count()
        finally:
            db.close()
        r = c.post("/api/admin/secrets", headers=HA, json={
            "ref_key": "webhook:alert", "value": "sk-secret-alert-NEW",
            "kind": "webhook", "pii_level": "low", "retention_days": 90, "region": "eu",
        })
        check("幂等 upsert 200", r.status_code == 200, r.text)
        db = SessionLocal()
        try:
            after = db.query(SecretEntry).filter(
                SecretEntry.company_id == CID, SecretEntry.ref_key == "webhook:alert").count()
            val = get_secret(db, CID, "webhook:alert")
        finally:
            db.close()
        check("行数不变", before == after == 1, f"before={before} after={after}")
        check("值已覆盖", val == "sk-secret-alert-NEW")

        # 5. DELETE 幂等
        r = c.delete("/api/admin/secrets/webhook:alert", headers=HA)
        check("DELETE 200", r.status_code == 200 and _unpack(r).get("ok") is True)
        r = c.delete("/api/admin/secrets/webhook:alert", headers=HA)
        check("DELETE 幂等", r.status_code == 200 and _unpack(r).get("ok") is True)
        db = SessionLocal()
        try:
            check("删除后无值", get_secret(db, CID, "webhook:alert") is None)
        finally:
            db.close()

        # 6. migrate 从 .env 迁移（不依赖真实 .env，临时写入）
        from app.api import admin as admin_mod
        env_path = admin_mod._ENV_FILE
        backup_text = env_path.read_text(encoding="utf-8") if env_path.exists() else None
        try:
            env_path.write_text("DEEPSEEK_API_KEY=sk-migrate-ds\nKIMI_API_KEY=sk-migrate-kimi\n",
                                encoding="utf-8", newline="\n")
            db = SessionLocal()
            try:
                res = migrate_env_to_keychain(db, CID, actor_name="tester")
            finally:
                db.close()
            check("migrate 迁 2 个", res["count"] == 2, str(res))
            check("migrate 含 llm:deepseek/kimi",
                  "llm:deepseek" in res["migrated"] and "llm:kimi" in res["migrated"])
            check("migrate 结果不回明文", "sk-migrate-ds" not in str(res))
            db = SessionLocal()
            try:
                check("Keychain 落库", get_secret(db, CID, "llm:deepseek") == "sk-migrate-ds")
            finally:
                db.close()
            db = SessionLocal()
            try:
                res2 = migrate_env_to_keychain(db, CID, actor_name="tester")
            finally:
                db.close()
            check("migrate 幂等", res2["count"] == 2, str(res2))
        finally:
            if backup_text is None:
                if env_path.exists():
                    env_path.unlink()
            else:
                env_path.write_text(backup_text, encoding="utf-8", newline="\n")

        # 7. resolve_llm_key：Keychain 优先，.env 兜底
        from app.config import settings
        db = SessionLocal()
        try:
            from app.store_secrets import delete_secret
            delete_secret(db, CID, "llm:deepseek", actor_name="tester")
            orig = settings.deepseek_key
            settings.deepseek_key = "sk-fallback-ds"
            check("resolve 兜底 .env", resolve_llm_key("deepseek", db=db, company_id=CID) == "sk-fallback-ds")
            set_secret(db, CID, "llm:deepseek", "sk-keychain-ds", kind="llm",
                       pii_level="high", actor_name="tester")
            check("resolve Keychain 优先", resolve_llm_key("deepseek", db=db, company_id=CID) == "sk-keychain-ds")
            settings.deepseek_key = orig
            delete_secret(db, CID, "llm:deepseek", actor_name="tester")
        finally:
            db.close()

        # 8. mask_secret 单元
        check("mask 空串", mask_secret("") == "")
        check("mask 短值全掩", mask_secret("sk-123") == "******")
        check("mask 不含明文", "123456" not in mask_secret("sk-secret-alert-123456"))
        check("mask 保留前缀", mask_secret("sk-secret-alert-123456").startswith("sk-s"))

    print(f"\nRESULT: PASS {len(PASS)} / FAIL {len(FAIL)} / SKIP 0")
    if FAIL:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
