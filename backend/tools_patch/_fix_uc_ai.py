# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\models_ai.py")
s = p.read_text(encoding="utf-8")
import re
m = re.search(r"from sqlalchemy import ([^\n]+)", s)
print("import line:", m.group(0) if m else None)
if m and "UniqueConstraint" not in m.group(1):
    s = s.replace(m.group(0), m.group(0).rstrip() + ", UniqueConstraint", 1)
    p.write_text(s, encoding="utf-8")
    print("OK added UniqueConstraint")
else:
    print("already has or not found")