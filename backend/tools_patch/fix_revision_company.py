# -*- coding: utf-8 -*-
from pathlib import Path
import ast
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\models_ontology.py")
t = p.read_text(encoding="utf-8")
o1 = 'def bump_revision(db, note: str = "") -> str:'
n1 = 'def bump_revision(db, note: str = "", company_id: int = 1) -> str:'
o2 = 'db.add(OntologySchemaRevision(revision=new_rev, note=note))'
n2 = 'db.add(OntologySchemaRevision(company_id=company_id, revision=new_rev, note=note))'
assert o1 in t and o2 in t, "anchor missing"
t = t.replace(o1, n1, 1).replace(o2, n2, 1)
p.write_text(t, encoding="utf-8")
ast.parse(t)
print("MODELS OK")
q = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\api\ontology_api.py")
u = q.read_text(encoding="utf-8")
o3 = "    new_version = bump_revision(db, note)"
n3 = "    new_version = bump_revision(db, note, company_id=user.company_id or 1)"
assert o3 in u, "api anchor missing"
u = u.replace(o3, n3, 1)
q.write_text(u, encoding="utf-8")
ast.parse(u)
print("API OK")