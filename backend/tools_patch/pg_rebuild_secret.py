# -*- coding: utf-8 -*-
"""PG 测试库：DROP 残留 secret_entries -> alembic upgrade head 重建（含 RLS policy）。"""
import os
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")
PY = ROOT / "venv" / "Scripts" / "python.exe"
PSQL = r"C:\Program Files\PostgreSQL\17\bin\psql.exe"
TEST_PG_URL = "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios_test"

env = dict(os.environ)
env["DATABASE_URL"] = TEST_PG_URL
env["PGPASSWORD"] = "postgres123"

# 1) 删残留表
p = subprocess.run([PSQL, "-h", "127.0.0.1", "-U", "postgres", "-d", "furui_aios_test",
                    "-c", 'DROP TABLE IF EXISTS secret_entries CASCADE'],
                   env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
print("=== drop secret_entries ===")
print(p.stdout.strip(), p.stderr.strip())
print(f"exit={p.returncode}")

# 2) upgrade head
p = subprocess.run([str(PY), "-m", "alembic", "upgrade", "head"],
                   cwd=str(ROOT), env=env, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=120)
print("\n=== upgrade head ===")
print(p.stdout[-2000:])
if p.stderr.strip():
    print("STDERR:", p.stderr[-2000:])
print(f"exit={p.returncode}")

# 3) 验证表与 RLS
p = subprocess.run([PSQL, "-h", "127.0.0.1", "-U", "postgres", "-d", "furui_aios_test",
                    "-c", "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='secret_entries';"],
                   env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
print("\n=== RLS 状态 ===")
print(p.stdout.strip(), p.stderr.strip())
p = subprocess.run([PSQL, "-h", "127.0.0.1", "-U", "postgres", "-d", "furui_aios_test",
                    "-c", "SELECT tablename, policyname FROM pg_policies WHERE tablename='secret_entries';"],
                   env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
print(p.stdout.strip(), p.stderr.strip())
