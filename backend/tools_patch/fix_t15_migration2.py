# -*- coding: utf-8 -*-
from pathlib import Path
V = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\alembic\versions")
old = V / "a1b2c3d4e5f6_app_pages.py"
# 覆盖为无 revision 的占位注释（alembic 扫描到无 revision 属性会警告并跳过）
old.write_text("# DISABLED - revision collision placeholder (superseded by a2b3c4d5e6f7_app_pages.py)\n", encoding="utf-8")
print("overwritten:", old.name, "size:", old.stat().st_size)
new = V / "a2b3c4d5e6f7_app_pages.py"
print("new exists:", new.exists())