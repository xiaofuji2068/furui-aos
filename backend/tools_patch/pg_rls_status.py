# -*- coding: utf-8 -*-
"""查 PG 生产库：各表 RLS 状态 + 无 RLS 的表。"""
import os
import subprocess

PSQL = r"C:\Program Files\PostgreSQL\17\bin\psql.exe"
env = dict(os.environ)
env["PGPASSWORD"] = "postgres123"

p = subprocess.run([PSQL, "-h", "127.0.0.1", "-U", "postgres", "-d", "furui_aios",
                    "-c", """
SELECT c.relname AS table_name,
       c.relrowsecurity AS rls,
       c.relforcerowsecurity AS force_rls,
       (SELECT count(*) FROM pg_policies p WHERE p.tablename = c.relname) AS policies
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r' AND n.nspname = 'public'
ORDER BY c.relname;
"""], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
print(p.stdout.strip())
if p.stderr.strip():
    print("ERR:", p.stderr.strip())
