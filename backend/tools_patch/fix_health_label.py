# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\api\health.py")
t = p.read_text(encoding="utf-8")
old = 'from ..db import SessionLocal'
new = 'from ..db import IS_SQLITE, SessionLocal'
assert old in t
t = t.replace(old, new, 1)
old2 = 'return {"name": "数据库", "status": "ok", "detail": "SQLite 连接正常"}'
new2 = 'return {"name": "数据库", "status": "ok", "detail": ("SQLite 连接正常" if IS_SQLITE else "PostgreSQL 连接正常")}'
assert old2 in t
t = t.replace(old2, new2, 1)
p.write_text(t, encoding="utf-8")
import ast; ast.parse(t)
print("health.py label fixed")