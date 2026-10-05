# -*- coding: utf-8 -*-
"""PG 测试库：stamp b2c3d4e5f6a7（标记已到旧 head）-> upgrade head（建 secret_entries + RLS）。"""
import os
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")
PY = ROOT / "venv" / "Scripts" / "python.exe"
TEST_PG = "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios_test"

env = dict(os.environ)
env["DATABASE_URL"] = TEST_PG

p = subprocess.run([str(PY), "-m", "alembic", "stamp", "b2c3d4e5f6a7"],
                   cwd=str(ROOT), env=env, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=120)
print("=== stamp b2c3d4e5f6a7 ===")
print(p.stdout[-1500:])
if p.stderr.strip():
    print("STDERR:", p.stderr[-1500:])
print(f"stamp exit={p.returncode}")

p = subprocess.run([str(PY), "-m", "alembic", "upgrade", "head"],
                   cwd=str(ROOT), env=env, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=120)
print("\n=== upgrade head ===")
print(p.stdout[-2000:])
if p.stderr.strip():
    print("STDERR:", p.stderr[-2000:])
print(f"upgrade exit={p.returncode}")
