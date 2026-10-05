# -*- coding: utf-8 -*-
"""TASK-013：test_secret_ref.py 适配跨方言——动态取 admin 用户 company_id，替换硬编码 1。"""
import io
import re

p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tests\test_secret_ref.py"
with io.open(p, "r", encoding="utf-8") as f:
    src = f.read()

# 1) main() 里登录后动态取 CID
old = """    with TestClient(app) as c:
        HA = _bearer(c)

        # 1. 无 token 被拒"""
new = """    with TestClient(app) as c:
        HA = _bearer(c)

        # 动态租户：SQLite 种子 admin.company_id=1；PG 种子可能不同（如 3）
        db0 = SessionLocal()
        try:
            from app.models import User
            CID = db0.query(User.company_id).filter(User.username == "admin").scalar() or 1
        finally:
            db0.close()
        print(f"[test] admin company_id={CID}")

        # 1. 无 token 被拒"""
if old not in src:
    print("WARN: main anchor not found")
    raise SystemExit(1)
src = src.replace(old, new, 1)

# 2) 幂等测试：company_id == 1 -> CID
src = src.replace('SecretEntry.company_id == 1, SecretEntry.ref_key == "webhook:alert"',
                  'SecretEntry.company_id == CID, SecretEntry.ref_key == "webhook:alert"')
src = src.replace("get_secret(db, 1, \"webhook:alert\")", "get_secret(db, CID, \"webhook:alert\")")

# 3) migrate：company_id=1 -> CID
src = src.replace("migrate_env_to_keychain(db, 1, actor_name=\"tester\")",
                  "migrate_env_to_keychain(db, CID, actor_name=\"tester\")")
src = src.replace("get_secret(db, 1, \"llm:deepseek\")", "get_secret(db, CID, \"llm:deepseek\")")
src = src.replace("get_secret(db, 1, \"llm:kimi\")", "get_secret(db, CID, \"llm:kimi\")")

# 4) resolve：delete/set_secret company_id=1 -> CID，resolve_llm_key 传 company_id
src = src.replace("delete_secret(db, 1, \"llm:deepseek\", actor_name=\"tester\")",
                  "delete_secret(db, CID, \"llm:deepseek\", actor_name=\"tester\")")
src = src.replace('set_secret(db, 1, "llm:deepseek", "sk-keychain-ds", kind="llm",',
                  'set_secret(db, CID, "llm:deepseek", "sk-keychain-ds", kind="llm",')
src = src.replace('resolve_llm_key("deepseek", db=db)',
                  'resolve_llm_key("deepseek", db=db, company_id=CID)')

with io.open(p, "w", encoding="utf-8") as f:
    f.write(src)
print("OK: test_secret_ref dynamic CID")
