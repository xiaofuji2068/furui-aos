# -*- coding: utf-8 -*-
import sqlite3, sys
print("py", sys.version)
db = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\data\app.db"
con = sqlite3.connect(db)
cur = con.cursor()
print("isolation_level:", con.isolation_level)
cur.execute("DROP TABLE IF EXISTS app_pages")
cur.execute("""CREATE TABLE app_pages (id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL DEFAULT 1)""")
print("after CREATE TABLE -> sqlite_master:")
print(cur.execute("SELECT type,name FROM sqlite_master WHERE name LIKE 'app_pages%'").fetchall())
print("PRAGMA database_list:", cur.execute("PRAGMA database_list").fetchall())
try:
    cur.execute("CREATE INDEX ix_test ON app_pages (company_id)")
    print("index OK")
except Exception as e:
    print("index ERR:", e)
con.commit()
con.close()