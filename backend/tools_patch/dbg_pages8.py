# -*- coding: utf-8 -*-
import sqlite3
db = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\data\app.db"
con = sqlite3.connect(db, autocommit=True)
cur = con.cursor()
print("integrity:", cur.execute("PRAGMA integrity_check").fetchone())
# 已有表上建索引
try:
    cur.execute("CREATE INDEX ix_zz_dbg ON companies (name)")
    print("index on companies OK:", cur.execute("SELECT name FROM sqlite_master WHERE name='ix_zz_dbg'").fetchall())
    cur.execute("DROP INDEX ix_zz_dbg")
    print("drop index OK")
except Exception as e:
    print("index err:", type(e).__name__, e)
# DROP 一张可重建的测试表看 DROP 是否生效
try:
    cur.execute("DROP TABLE IF EXISTS logic_nodes_dbg_zz")
    print("drop noexist OK")
except Exception as e:
    print("drop err:", e)
# CREATE TEMP TABLE（temp schema）是否生效
cur.execute("CREATE TEMP TABLE tt_dbg (id INTEGER)")
print("temp table:", cur.execute("SELECT name FROM sqlite_temp_master WHERE name='tt_dbg'").fetchall())
# ATTACH 一个内存库再建表
cur.execute("ATTACH DATABASE ':memory:' AS memdb")
cur.execute("CREATE TABLE memdb.mm (id INTEGER)")
print("attached mem:", cur.execute("SELECT name FROM memdb.sqlite_master WHERE name='mm'").fetchall())
con.close()