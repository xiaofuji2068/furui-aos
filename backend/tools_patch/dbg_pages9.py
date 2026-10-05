# -*- coding: utf-8 -*-
import sqlite3, shutil, os
db = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\data\app.db"
attr = os.stat(db).st_file_attributes
print("file attributes: 0x%X" % attr)
print("OFFLINE(0x1000):", bool(attr & 0x1000), "| RECALL_ON_OPEN(0x40000):", bool(attr & 0x40000), "| RECALL_ON_DATA(0x400000):", bool(attr & 0x400000))
print("st_size:", os.path.getsize(db))
# 复制到系统 temp（非用户目录）再建表
dst = os.path.join(os.environ["TEMP"], "app_copy.db")
shutil.copy2(db, dst)
con = sqlite3.connect(dst, autocommit=True)
cur = con.cursor()
cur.execute("CREATE TABLE t_copy (id INTEGER PRIMARY KEY)")
print("copy in TEMP has t_copy:", cur.execute("SELECT name FROM sqlite_master WHERE name='t_copy'").fetchall())
cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()
print("copy total tables:", cur.fetchone())
con.close()
os.remove(dst)