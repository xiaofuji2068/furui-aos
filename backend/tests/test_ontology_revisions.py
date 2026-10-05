"""3.X.2 动作表 #1：bump_revision 接通 API（Task #31-#33）。

锁定：
- POST /api/ontology/revisions 接收 note → 写 OntologySchemaRevision → 返回新版本号
- 权限：knowledge:manage（admin 有，sales 没有）
- 同 store（公司）下版本号递增且唯一（与 bump_revision 语义对齐）
- GET /api/ontology/revisions 按 commit_ts 倒序返回全部
- 审计：每次 POST 写 AuditLog，action="ontology.bump_revision"

依赖：
- 启动时 seed_ontology 已落 r1 基线
- admin / sales 用户存在（bootstrap 默认种子）

运行：
    backend/venv/Scripts/python.exe tests/test_ontology_revisions.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models_ai import AuditLog  # noqa: E402
from app.models import Company  # noqa: E402
from app.models_ontology import OntologySchemaRevision  # noqa: E402

PASS, FAIL = [], []


def check(name: str, cond: bool, extra: str = ""):
    (PASS if cond else FAIL).append(name)
    print(f"{'  PASS' if cond else '  FAIL'}  {name}" + (f"  <{extra}>" if extra and not cond else ""))


def _login(c: TestClient, username: str, password: str) -> str | None:
    r = c.post("/api/auth/login", json={"username": username, "password": password})
    if r.status_code != 200:
        return None
    try:
        return r.json()["data"]["token"]
    except (KeyError, TypeError):
        return None


def main():
    with TestClient(app) as c:
        print("=== 未登录访问被拒 ===")
        r = c.get("/api/ontology/revisions")
        check("GET 无 token 401", r.status_code == 401, str(r.status_code))
        r = c.post("/api/ontology/revisions", json={"note": "x"})
        check("POST 无 token 401", r.status_code == 401, str(r.status_code))

        print("\n=== sales 登录（无 knowledge:manage） ===")
        sales_tok = _login(c, "sales", "123456")
        check("sales 登录成功", bool(sales_tok))
        HS = {"Authorization": f"Bearer {sales_tok}"} if sales_tok else {}
        if sales_tok:
            r = c.get("/api/ontology/revisions", headers=HS)
            check("sales GET revisions 200（datasource:view 可读）",
                  r.status_code == 200, str(r.status_code))
            r = c.post("/api/ontology/revisions", headers=HS, json={"note": "sales attempt"})
            check("sales POST revisions 403（knowledge:manage 缺失）",
                  r.status_code == 403, str(r.status_code))

        print("\n=== admin 登录（有 knowledge:manage） ===")
        admin_tok = _login(c, "admin", "123456")
        check("admin 登录成功", bool(admin_tok))
        HA = {"Authorization": f"Bearer {admin_tok}"} if admin_tok else {}
        if not admin_tok:
            print("  无法继续：admin 登录失败")
            print(f"\n=== 结果：PASS {len(PASS)} / FAIL {len(FAIL)} ===")
            return 1

        # 记录 baseline，测试结束时清理
        db = SessionLocal()
        cid = db.query(Company).order_by(Company.id).first().id
        baseline = {r.revision for r in db.query(OntologySchemaRevision).filter(OntologySchemaRevision.company_id == cid).all()}
        baseline_count = len(baseline)
        print(f"  baseline 版本数：{baseline_count} ({sorted(baseline)})")
        check("baseline 含 r1", "r1" in baseline, str(sorted(baseline)))

        # 记录 audit log 起点
        audit_baseline = db.query(AuditLog).filter(
            AuditLog.action == "ontology.bump_revision"
        ).count()

        print("\n=== POST /api/ontology/revisions 递增三次 ===")
        versions = []
        for i in range(3):
            r = c.post(
                "/api/ontology/revisions",
                headers=HA,
                json={"note": f"测试 #1.{i} 模拟新增字段"},
            )
            check(f"POST 第 {i+1} 次 200", r.status_code == 200,
                  str(r.status_code) + " " + r.text[:120])
            if r.status_code == 200:
                body = r.json().get("data", r.json())  # 兼容 envelope 与裸 dict
                check(f"POST 第 {i+1} 次 含 version 字段", "version" in body)
                check(f"POST 第 {i+1} 次 含 commit_ts 字段", "commit_ts" in body)
                check(f"POST 第 {i+1} 次 version 形如 rN",
                      body.get("version", "").startswith("r"),
                      str(body.get("version")))
                versions.append(body.get("version"))

        check("三次版本号唯一", len(set(versions)) == 3, str(versions))
        check("三次版本号递增",
              versions == sorted(versions, key=lambda v: int(v[1:])),
              str(versions))
        check("三次版本号均不在 baseline",
              all(v not in baseline for v in versions),
              str(versions))

        # 验证数据库实际写入
        db.expire_all()
        revs_now = sorted(r.revision for r in db.query(OntologySchemaRevision).filter(OntologySchemaRevision.company_id == cid).all())
        check("DB 总版本数 = baseline + 3",
              len(revs_now) == baseline_count + 3,
              f"{baseline_count} -> {len(revs_now)} ({revs_now})")

        # 验证审计
        audit_now = db.query(AuditLog).filter(
            AuditLog.action == "ontology.bump_revision"
        ).count()
        check(f"AuditLog 增量 = 3（{audit_baseline} -> {audit_now}）",
              audit_now - audit_baseline == 3,
              f"{audit_baseline} -> {audit_now}")

        print("\n=== POST 空 note 自动用 manual bump by <user> 兜底 ===")
        r = c.post("/api/ontology/revisions", headers=HA, json={"note": ""})
        check("POST 空 note 200", r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            note = r.json().get("data", {}).get("note", "")
            check("空 note 时回退为 manual bump by ...",
                  note.startswith("manual bump by"), note)

        print("\n=== GET /api/ontology/revisions 按 commit_ts 倒序 ===")
        r = c.get("/api/ontology/revisions", headers=HA)
        check("GET 200", r.status_code == 200, str(r.status_code))
        items = r.json().get("data", r.json()) if r.status_code == 200 else []
        check("返回是列表", isinstance(items, list))
        check("列表至少含 baseline + 4 条", len(items) >= baseline_count + 4,
              f"baseline={baseline_count} items={len(items)}")
        if items:
            ts_list = [it.get("commit_ts") for it in items]
            check("按 commit_ts 倒序", ts_list == sorted(ts_list, reverse=True),
                  str(ts_list[:3]))
            check("每条含 version + note + commit_ts",
                  all({"version", "note", "commit_ts"} <= set(it.keys()) for it in items),
                  str(items[0]))

        # 清理测试产生的 revision（保留 baseline）
        for r in db.query(OntologySchemaRevision).filter(OntologySchemaRevision.company_id == cid).all():
            if r.revision not in baseline:
                db.delete(r)
        db.commit()
        # 清理测试产生的 audit log（保留业务审计）
        db.query(AuditLog).filter(
            AuditLog.action == "ontology.bump_revision",
            AuditLog.target.like("r%"),
        ).delete(synchronize_session=False)
        db.commit()
        print("\n（已清理本次测试产生的 revision / audit 行）")

    print(f"\n=== 结果：PASS {len(PASS)} / FAIL {len(FAIL)} ===")
    if FAIL:
        print("失败：", FAIL)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
