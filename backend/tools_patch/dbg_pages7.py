# -*- coding: utf-8 -*-
import sqlite3, tempfile, os
# 全新文件
p = os.path.join(tempfile.gettempdir(), "zz_sqlite_test.db")
if os.path.exists(p):
    os.remove(p)
con = sqlite3.connect(p)
cur = con.cursor()
cur.execute("CREATE TABLE t1 (id INTEGER PRIMARY KEY)")
print("fresh file:", cur.execute("SELECT name FROM sqlite_master WHERE name='t1'").fetchall())
con.commit(); con.close()
os.remove(p)
# app.db 只读属性检查
db = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\data\app.db"
print("app.db readonly attr:", os.stat(db).st_file_attributes & 1)
# 尝试 PRAGMA quick_check
con2 = sqlite3.connect(db, autocommit=True)
try:
    print("quick_check:", con2.execute("PRAGMA quick_check").fetchone())
except Exception as e:
    print("quick_check err:", e)
con2.close()