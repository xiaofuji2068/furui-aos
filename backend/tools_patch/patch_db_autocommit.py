# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\db.py")
s = p.read_text(encoding="utf-8")
old = 'engine_kwargs["connect_args"] = {"check_same_thread": False}   # SQLite + FastAPI 多线程'
new = ('engine_kwargs["connect_args"] = {"check_same_thread": False,   # SQLite + FastAPI 多线程\n'
       '                                   "isolation_level": None}     # autocommit：DDL 立即落库（Python 3.12+ sqlite3 默认把 DDL 包进延迟事务）')
assert old in s
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")
print("OK db.py autocommit")