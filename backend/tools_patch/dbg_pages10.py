# -*- coding: utf-8 -*-
import sqlite3, shutil, os
db = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\data\app.db"
dst = os.path.join(os.environ["TEMP"], "app_copy.db")
# 确保副本干净（删掉测试表）
con = sqlite3.connect(dst, autocommit=True)
con.execute("DROP TABLE IF EXISTS t_copy")
con.close()
# 备份原文件后覆盖
bak = db + ".bak_20260924"
if not os.path.exists(bak):
    shutil.copy2(db, bak)
shutil.copy2(dst, db)
print("replaced. new size:", os.path.getsize(db))
# 原路径验证建表
con2 = sqlite3.connect(db, autocommit=True)
cur2 = con2.cursor()
cur2.execute("CREATE TABLE app_pages (id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL DEFAULT 1, code VARCHAR(64) NOT NULL, title VARCHAR(128) NOT NULL DEFAULT '', description VARCHAR(500) NOT NULL DEFAULT '', status VARCHAR(16) NOT NULL DEFAULT 'draft', version VARCHAR(32) NOT NULL DEFAULT '1.0', layout_json TEXT NOT NULL DEFAULT '[]', created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE (company_id, code))")
print("orig path app_pages:", cur2.execute("SELECT name FROM sqlite_master WHERE name='app_pages'").fetchall())
cur2.execute("CREATE INDEX ix_app_pages_company_id ON app_pages (company_id)")
print("index OK")
con2.close()
print("BAK saved at:", bak)