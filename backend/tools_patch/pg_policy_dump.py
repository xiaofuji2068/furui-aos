# -*- coding: utf-8 -*-
"""查 users 及代表性表的 RLS policy 定义 + current_setting 行为。"""
import os
import subprocess

PSQL = r"C:\Program Files\PostgreSQL\17\bin\psql.exe"
env = dict(os.environ)
env["PGPASSWORD"] = "postgres123"

SQL = """
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
FROM pg_policies
WHERE tablename IN ('users', 'companies', 'agent_tasks', 'secret_entries')
ORDER BY tablename, policyname;
"""
p = subprocess.run([PSQL, "-h", "127.0.0.1", "-U", "postgres", "-d", "furui_aios_test",
                    "-c", SQL], env=env, capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print(p.stdout.strip())
if p.stderr.strip():
    print("ERR:", p.stderr.strip())
