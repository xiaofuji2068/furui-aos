# -*- coding: utf-8 -*-
"""TASK-020：建受限角色 furui_app（生产库+测试库），只授 DML/序列，无 DDL。

使应用连接不再使用 superuser postgres：furui_app 非表 owner，
RLS 策略天然生效（policy 按 app.company_id 过滤）。
"""
import os
import subprocess

PSQL = r"C:\Program Files\PostgreSQL\17\bin\psql.exe"
env = dict(os.environ)
env["PGPASSWORD"] = "postgres123"

SQL = """
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'furui_app') THEN
    CREATE ROLE furui_app LOGIN PASSWORD 'furui_app_local';
  END IF;
END
$$;
GRANT CONNECT ON DATABASE %DB% TO furui_app;
GRANT USAGE ON SCHEMA public TO furui_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO furui_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO furui_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO furui_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO furui_app;
"""

for dbname in ["furui_aios", "furui_aios_test"]:
    sql = SQL.replace("%DB%", dbname)
    p = subprocess.run([PSQL, "-h", "127.0.0.1", "-U", "postgres", "-d", dbname, "-c", sql],
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"=== {dbname} ===")
    print(p.stdout.strip() if p.stdout.strip() else "(ok)")
    if p.stderr.strip():
        print("ERR:", p.stderr.strip())
    print(f"exit={p.returncode}")
