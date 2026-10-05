# -*- coding: utf-8 -*-
"""TASK-015：PG 双库 upgrade head（a1b2c3d4e5f6 = app_pages）+ RLS 验证。"""
import os
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")
PY = ROOT / "venv" / "Scripts" / "python.exe"
PSQL = r"C:\Program Files\PostgreSQL\17\bin\psql.exe"

for db in ("furui_aios", "furui_aios_test"):
    print(f"\n===== {db} =====")
    env = dict(os.environ)
    env["DATABASE_URL"] = f"postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/{db}"
    env["PGPASSWORD"] = "postgres123"
    p = subprocess.run([PSQL, "-h", "127.0.0.1", "-U", "postgres", "-d", db,
                        "-t", "-A", "-c", "SELECT version_num FROM alembic_version;"],
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    print("before:", p.stdout.strip() or p.stderr.strip()[:200])
    p = subprocess.run([str(PY), "-m", "alembic", "upgrade", "head"],
                       cwd=str(ROOT), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=180)
    out = (p.stdout or "")[-1500:]
    err = (p.stderr or "")[-800:]
    print("upgrade exit:", p.returncode)
    print(out)
    if err:
        print("STDERR:", err)
    p = subprocess.run([PSQL, "-h", "127.0.0.1", "-U", "postgres", "-d", db,
                        "-t", "-A", "-c", "SELECT version_num FROM alembic_version;"],
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    print("after:", p.stdout.strip())
    p = subprocess.run([PSQL, "-h", "127.0.0.1", "-U", "postgres", "-d", db,
                        "-t", "-A", "-c", "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='app_pages';"],
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    print("app_pages RLS:", p.stdout.strip() or "(no row)")