# -*- coding: utf-8 -*-
import sqlite3
db = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\data\app.db"
con = sqlite3.connect(db)
cur = con.cursor()
cur.execute("DROP TABLE IF EXISTS app_pages")
cur.execute("""CREATE TABLE app_pages (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL DEFAULT 1,
    code VARCHAR(64) NOT NULL,
    title VARCHAR(128) NOT NULL DEFAULT '',
    description VARCHAR(500) NOT NULL DEFAULT '',
    status VARCHAR(16) NOT NULL DEFAULT 'draft',
    version VARCHAR(32) NOT NULL DEFAULT '1.0',
    layout_json TEXT NOT NULL DEFAULT '[]',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (company_id, code)
)""")
cur.execute("CREATE INDEX ix_app_pages_company_id ON app_pages (company_id)")
con.commit()
rows = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='app_pages'").fetchall()
print("raw sqlite rows:", rows)
con.close()