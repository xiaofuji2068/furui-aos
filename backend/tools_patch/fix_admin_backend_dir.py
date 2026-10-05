# -*- coding: utf-8 -*-
"""TASK-013：修复 admin.py _BACKEND_DIR 路径（少一层，应为 backend/）。"""
import io

p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\api\admin.py"
with io.open(p, "r", encoding="utf-8") as f:
    src = f.read()

old = '_BACKEND_DIR = Path(__file__).resolve().parent.parent          # backend/'
new = '_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent   # backend/'
if old not in src:
    print("WARN: _BACKEND_DIR anchor not found")
    raise SystemExit(1)
src = src.replace(old, new, 1)
with io.open(p, "w", encoding="utf-8") as f:
    f.write(src)
print("OK: _BACKEND_DIR fixed -> backend/")
