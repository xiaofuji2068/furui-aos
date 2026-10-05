# -*- coding: utf-8 -*-
import os, shutil, sqlite3
bak = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\data\app.db.bak_20260924"
target_dir = os.path.join(os.environ["LOCALAPPDATA"], "FuruiAIOS", "data")
os.makedirs(target_dir, exist_ok=True)
dst = os.path.join(target_dir, "app.db")
shutil.copy2(bak, dst)
print("restored size:", os.path.getsize(dst))
con = sqlite3.connect(dst, autocommit=True)
cur = con.cursor()
print("tables:", cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0])
print("companies:", cur.execute("SELECT count(*) FROM companies").fetchone()[0])
cur.execute("CREATE TABLE zz_ok (id INTEGER PRIMARY KEY)")
cur.execute("DROP TABLE zz_ok")
print("DDL OK")
con.close()
print("TARGET:", dst)