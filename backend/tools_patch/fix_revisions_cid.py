# -*- coding: utf-8 -*-
from pathlib import Path
import ast
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tests\test_ontology_revisions.py")
t = p.read_text(encoding="utf-8")
reps = [
    ("from app.models_ontology import OntologySchemaRevision  # noqa: E402",
     "from app.models import Company  # noqa: E402\nfrom app.models_ontology import OntologySchemaRevision  # noqa: E402"),
    ("        db = SessionLocal()\n        baseline = {r.revision for r in db.query(OntologySchemaRevision).all()}",
     "        db = SessionLocal()\n        cid = db.query(Company).order_by(Company.id).first().id\n        baseline = {r.revision for r in db.query(OntologySchemaRevision).filter(OntologySchemaRevision.company_id == cid).all()}"),
    ("revs_now = sorted(r.revision for r in db.query(OntologySchemaRevision).all())",
     "revs_now = sorted(r.revision for r in db.query(OntologySchemaRevision).filter(OntologySchemaRevision.company_id == cid).all())"),
    ("        for r in db.query(OntologySchemaRevision).all():",
     "        for r in db.query(OntologySchemaRevision).filter(OntologySchemaRevision.company_id == cid).all():"),
]
n = 0
for o, nw in reps:
    c = t.count(o)
    if c:
        t = t.replace(o, nw)
        n += c
    else:
        print("MISS:", o[:60])
p.write_text(t, encoding="utf-8")
ast.parse(p.read_text(encoding="utf-8"))
print("PATCHED", n, "SYNTAX OK")