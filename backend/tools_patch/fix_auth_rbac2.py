# -*- coding: utf-8 -*-
from pathlib import Path
import ast
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tests\test_auth_rbac.py")
t = p.read_text(encoding="utf-8")

# 1) import 补齐
old = "from app.main import app  # noqa: E402\n\nclient: TestClient | None = None"
new = ("from app.main import app  # noqa: E402\n"
       "from app.db import SessionLocal  # noqa: E402\n"
       "from app.models import Company, User  # noqa: E402\n\n"
       "client: TestClient | None = None")
if old in t:
    t = t.replace(old, new, 1)
    print("IMPORT OK")
else:
    print("IMPORT MISS")

# 2) _run() 开头定义 db + cid
old = "def _run():\n    print(\"\\n=== TASK-002 用户登录 / 信息 / 退出 ===\")"
new = ("def _run():\n"
       "    db = SessionLocal()\n"
       "    cid = getattr(db.query(Company).order_by(Company.id).first(), \"id\", 1)\n"
       "    print(\"\\n=== TASK-002 用户登录 / 信息 / 退出 ===\")")
if old in t:
    t = t.replace(old, new, 1)
    print("DBDEF OK")
else:
    print("DBDEF MISS")

p.write_text(t, encoding="utf-8")
ast.parse(t)
print("SYNTAX OK")