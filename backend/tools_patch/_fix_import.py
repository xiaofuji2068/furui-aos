# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\models.py")
s = p.read_text(encoding="utf-8")
old = "from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Table, Column, Text, text"
new = "from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Table, Column, Text, text, UniqueConstraint"
assert old in s
p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("OK import fixed")