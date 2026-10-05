# -*- coding: utf-8 -*-
"""生产库 furui_aios：确认 alembic 版本 -> upgrade head（新增 secret_entries + RLS）。"""
import os
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")
PY = ROOT / "venv" / "Scripts" / "python.exe"
PSQL = r"C:\Program Files\PostgreSQL\17\bin\psql.exe"
PROD_PG = "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios"

env = dict(os.environ)
env["DATABASE_URL"] = PROD_PG
env["PGPASSWORD"] = "postgres123"

p = subprocess.run([PSQL, "-h", "127.0.0.1", "-U", "postgres", "-d", "furui_aios",
                    "-c", "SELECT version_num FROM alembic_version;"],
                   env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
print("=== 当前 alembic_version ===")
print(p.stdout.strip(), p.stderr.strip())

p = subprocess.run([str(PY), "-m", "alembic", "upgrade", "head"],
                   cwd=str(ROOT), env=env, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=120)
print("\n=== upgrade head ===")
print(p.stdout[-2000:])
if p.stderr.strip():
    print("STDERR:", p.stderr[-2000:])
print(f"exit={p.returncode}")

p = subprocess.run([PSQL, "-h", "127.0.0.1", "-U", "postgres", "-d", "furui_aios",
                    "-c", "SELECT version_num FROM alembic_version;"],
                   env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
print("\n=== 迁移后 alembic_version ===")
print(p.stdout.strip(), p.stderr.strip())

p = subprocess.run([PSQL, "-h", "127.0.0.1", "-U", "postgres", "-d", "furui_aios",
                    "-c", "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='secret_entries';"],
                   env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
print("\n=== secret_entries RLS 状态 ===")
print(p.stdout.strip(), p.stderr.strip())
