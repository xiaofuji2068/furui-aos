# -*- coding: utf-8 -*-
"""全量导出 public schema 所有 policy + 所有 RLS 表，交叉核对。"""
import os
import subprocess

PSQL = r"C:\Program Files\PostgreSQL\17\bin\psql.exe"
env = dict(os.environ)
env["PGPASSWORD"] = "postgres123"

p = subprocess.run([PSQL, "-h", "127.0.0.1", "-U", "postgres", "-d", "furui_aios_test",
                    "-c", """
SELECT tablename, policyname, cmd, roles
FROM pg_policies WHERE schemaname='public'
ORDER BY tablename, policyname;
"""], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
print("=== ALL POLICIES ===")
print(p.stdout.strip())
if p.stderr.strip():
    print("ERR:", p.stderr.strip())

p = subprocess.run([PSQL, "-h", "127.0.0.1", "-U", "postgres", "-d", "furui_aios_test",
                    "-c", """
SELECT relname, relrowsecurity, relforcerowsecurity
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE c.relkind='r' AND n.nspname='public'
ORDER BY relname;
"""], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
print("\n=== RLS FLAGS ===")
print(p.stdout.strip())
