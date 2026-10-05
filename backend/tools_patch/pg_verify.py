# -*- coding: utf-8 -*-
"""PG 验证：测试库 alembic upgrade head + PG 模式跑 secret_ref / rls_isolation。"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")
PY = ROOT / "venv" / "Scripts" / "python.exe"
TEST_PG = "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios_test"

# 1. 测试库迁移到 head（新增 secret_entries + RLS）
env = dict(os.environ)
env["DATABASE_URL"] = TEST_PG
print("===== 1) alembic upgrade head (furui_aios_test) =====", flush=True)
p = subprocess.run([str(PY), "-m", "alembic", "upgrade", "head"],
                   cwd=str(ROOT), env=env, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=120)
print(p.stdout[-2000:])
if p.stderr.strip():
    print("STDERR:", p.stderr[-2000:])
print(f"--- alembic exit={p.returncode}", flush=True)

# 2. PG 模式跑 test_secret_ref
env["TEST_PG_URL"] = TEST_PG
print("\n===== 2) test_secret_ref.py (PG mode) =====", flush=True)
p = subprocess.run([str(PY), "tests/test_secret_ref.py"], cwd=str(ROOT), env=env,
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
print(p.stdout[-2500:])
if p.stderr.strip():
    print("STDERR:", p.stderr[-2000:])
print(f"--- secret_ref PG exit={p.returncode}", flush=True)

# 3. PG 模式跑 test_rls_isolation
print("\n===== 3) test_rls_isolation.py (PG mode) =====", flush=True)
p = subprocess.run([str(PY), "tests/test_rls_isolation.py"], cwd=str(ROOT), env=env,
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
print(p.stdout[-2500:])
if p.stderr.strip():
    print("STDERR:", p.stderr[-2000:])
print(f"--- rls PG exit={p.returncode}", flush=True)

print("\nDONE")
