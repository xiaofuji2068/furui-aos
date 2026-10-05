# -*- coding: utf-8 -*-
"""TASK-014：PG 双库 upgrade head（f6a7b8c9d0e1）+ logic 表 RLS 核对。psycopg3。"""
import os, subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")
PY = ROOT / "venv" / "Scripts" / "python.exe"
PSQL = r"C:\Program Files\PostgreSQL\17\bin\psql.exe"
os.environ["PGPASSWORD"] = "postgres123"

for db in ("furui_aios", "furui_aios_test"):
    print(f"\n=== {db} upgrade head ===")
    env = dict(os.environ)
    env["DATABASE_URL"] = f"postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/{db}"
    r = subprocess.run([str(PY), "-m", "alembic", "upgrade", "head"],
                       cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=120)
    out = (r.stdout or "") + (r.stderr or "")
    print(out[-1400:])
    if r.returncode == 0:
        v = subprocess.run([PSQL, "-U", "postgres", "-d", db, "-t", "-c",
                            "SELECT version_num FROM alembic_version;"],
                           capture_output=True, text=True)
        print("alembic_version:", v.stdout.strip())
        q = subprocess.run([PSQL, "-U", "postgres", "-d", db, "-t", "-c",
                            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
                            "WHERE relname IN ('logic_graphs','logic_nodes') ORDER BY relname;"],
                           capture_output=True, text=True)
        print("logic tables RLS:\n" + (q.stdout or q.stderr))