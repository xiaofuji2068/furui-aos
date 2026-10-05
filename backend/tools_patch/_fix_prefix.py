# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\api\logic_api.py")
s = p.read_text(encoding="utf-8")
old = 'router = APIRouter(prefix="/api/logic", tags=["logic"])'
new = 'router = APIRouter(prefix="/logic", tags=["logic"])'
assert old in s
p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("OK prefix fixed")