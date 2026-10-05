# -*- coding: utf-8 -*-
import sqlite3
db = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\data\app.db"
# 新式 autocommit=True
con = sqlite3.connect(db, autocommit=True)
cur = con.cursor()
cur.execute("CREATE TABLE t_zzz2 (id INTEGER PRIMARY KEY)")
print("autocommit=True t_zzz2:", cur.execute("SELECT name FROM sqlite_master WHERE name='t_zzz2'").fetchall())
con.close()
# 对照：legacy + 显式 commit
con2 = sqlite3.connect(db)
cur2 = con2.cursor()
cur2.execute("CREATE TABLE t_zzz3 (id INTEGER PRIMARY KEY)")
print("legacy before commit:", cur2.execute("SELECT name FROM sqlite_master WHERE name='t_zzz3'").fetchall())
con2.commit()
print("legacy after commit:", cur2.execute("SELECT name FROM sqlite_master WHERE name='t_zzz3'").fetchall())
cur2.execute("DROP TABLE t_zzz3")
con2.commit()
con2.close()