# -*- coding: utf-8 -*-
"""TASK-020：测试库 upgrade head（对齐迁移 d4e5f6a7b8c9）+ RLS 状态核对。"""
import os
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")
PY = ROOT / "venv" / "Scripts" / "python.exe"

env = dict(os.environ)
env["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios_test"
env["PGPASSWORD"] = "postgres123"

p = subprocess.run([str(PY), "-m", "alembic", "upgrade", "head"],
                   cwd=str(ROOT), env=env, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=180)
print(p.stdout[-3000:])
if p.stderr.strip():
    print("STDERR:", p.stderr[-3000:])
print(f"exit={p.returncode}")
