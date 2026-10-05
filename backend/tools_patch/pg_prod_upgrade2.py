# -*- coding: utf-8 -*-
"""TASK-020：生产库 furui_aios upgrade head（对齐迁移 + 全库 RLS 收口）+ RLS 核对。"""
import os
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")
PY = ROOT / "venv" / "Scripts" / "python.exe"
PSQL = r"C:\Program Files\PostgreSQL\17\bin\psql.exe"

env = dict(os.environ)
env["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios"
env["PGPASSWORD"] = "postgres123"

p = subprocess.run([str(PY), "-m", "alembic", "upgrade", "head"],
                   cwd=str(ROOT), env=env, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=240)
print(p.stdout[-2000:])
if p.stderr.strip():
    print("STDERR:", p.stderr[-2000:])
print(f"exit={p.returncode}")

p = subprocess.run([PSQL, "-h", "127.0.0.1", "-U", "postgres", "-d", "furui_aios",
                    "-c", """
SELECT c.relname, c.relrowsecurity AS rls, c.relforcerowsecurity AS force_rls
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE c.relkind='r' AND n.nspname='public'
ORDER BY c.relname;
"""], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
print("\n=== 生产库 RLS 状态 ===")
print(p.stdout.strip())
rls_n = sum(1 for l in p.stdout.splitlines() if l.strip() and "|" in l and l.split("|")[1].strip() == "t")
print(f"RLS 表数: {rls_n}")
