# -*- coding: utf-8 -*-
import sqlite3
db = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\data\app.db"
con = sqlite3.connect(db, isolation_level=None)
cur = con.cursor()
print("before: total tables =", cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0])
cur.execute("DROP TABLE IF EXISTS app_pages")
cur.execute("SELECT count(*) FROM sqlite_master WHERE name='app_pages'").fetchone()
print("has app_pages row anywhere:", cur.execute("SELECT type,name FROM sqlite_master WHERE name='app_pages'").fetchall())
print("temp master:", cur.execute("SELECT type,name FROM sqlite_temp_master WHERE name='app_pages'").fetchall())
cur.execute("""CREATE TABLE app_pages (id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL DEFAULT 1)""")
print("after CT: total tables =", cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0])
print("table_info:", cur.execute("PRAGMA table_info('app_pages')").fetchall())
try:
    print("schema_version:", cur.execute("PRAGMA schema_version").fetchone())
    print("journal_mode:", cur.execute("PRAGMA journal_mode").fetchone())
except Exception as e:
    print("pragma err", e)
con.close()
print("--- reopen ---")
con2 = sqlite3.connect(db)
cur2 = con2.cursor()
print("reopen has app_pages:", cur2.execute("SELECT name FROM sqlite_master WHERE name='app_pages'").fetchall())
con2.close()