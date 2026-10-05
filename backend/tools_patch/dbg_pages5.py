# -*- coding: utf-8 -*-
import sqlite3
db = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\data\app.db"
con = sqlite3.connect(db, isolation_level=None)
cur = con.cursor()
cur.execute("CREATE TABLE t_zzz_test (id INTEGER PRIMARY KEY)")
print("t_zzz after CT:", cur.execute("SELECT type,name FROM sqlite_master WHERE name='t_zzz_test'").fetchall())
cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()
print("triggers referencing app_pages:", cur.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND (sql LIKE '%app_pages%')").fetchall())
print("views:", cur.execute("SELECT name FROM sqlite_master WHERE type='view' AND name LIKE '%page%'").fetchall())
cur.execute("DROP TABLE t_zzz_test")
con.close()