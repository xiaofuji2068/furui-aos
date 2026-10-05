# -*- coding: utf-8 -*-
"""查 PG 测试库 companies/users 实际数据。"""
import os
import subprocess

PSQL = r"C:\Program Files\PostgreSQL\17\bin\psql.exe"
env = dict(os.environ)
env["PGPASSWORD"] = "postgres123"

for sql, label in [
    ("SELECT id, name FROM companies ORDER BY id LIMIT 10;", "companies"),
    ("SELECT id, company_id, username, role FROM users ORDER BY id LIMIT 10;", "users"),
]:
    p = subprocess.run([PSQL, "-h", "127.0.0.1", "-U", "postgres", "-d", "furui_aios_test",
                        "-c", sql], env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    print(f"=== {label} ===")
    print(p.stdout.strip(), p.stderr.strip())
