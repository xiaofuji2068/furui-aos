# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tests\test_pages.py")
t = p.read_text(encoding="utf-8")
old = '        c = db.query(Company).filter(Company.code == "furui").first()\n        cid = c.id if c else 1'
new = '        c = db.query(Company).order_by(Company.id).first()\n        cid = c.id if c else 1'
if old in t:
    t = t.replace(old, new)
    p.write_text(t, encoding="utf-8")
    print("patched")
else:
    print("PATTERN NOT FOUND")