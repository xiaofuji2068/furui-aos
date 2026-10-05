# -*- coding: utf-8 -*-
from pathlib import Path
import ast
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\bootstrap.py")
t = p.read_text(encoding="utf-8")
o = "        seed_ontology(db)                      # 本体持久化种子（Phase 1 P0）"
n = ("        _fc = db.query(Company).order_by(Company.id).first()\n"
     "        seed_ontology(db, company_id=_fc.id if _fc else 1)  # 本体归属当前企业（Phase 1 P0）")
assert o in t, "anchor missing"
t = t.replace(o, n, 1)
p.write_text(t, encoding="utf-8")
ast.parse(t)
print("BOOTSTRAP OK")