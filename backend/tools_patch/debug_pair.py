# -*- coding: utf-8 -*-
"""复现：按批量顺序跑 test_admin_keys + test_api_mainline，dump 完整输出。"""
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")
PY = ROOT / "venv" / "Scripts" / "python.exe"

for name in ["test_admin_keys.py", "test_api_mainline.py"]:
    t = ROOT / "tests" / name
    print(f"\n========== {name} ==========")
    p = subprocess.run([str(PY), str(t)], cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=240)
    print("STDOUT:")
    print(p.stdout[-4000:])
    if p.stderr.strip():
        print("STDERR:")
        print(p.stderr[-4000:])
    print(f"--- {name}: exit={p.returncode}")
