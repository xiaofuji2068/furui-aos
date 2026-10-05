# -*- coding: utf-8 -*-
from pathlib import Path
import ast
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tests\test_outbox_projector.py")
t = p.read_text(encoding="utf-8")
pairs = [
    ('baseline_links = db.query(OntologyLinkRow).count()',
     'baseline_links = db.query(OntologyLinkRow).filter(OntologyLinkRow.company_id == cid).count()'),
    ('baseline_nodes = db.query(OntologyObjectRow).count()',
     'baseline_nodes = db.query(OntologyObjectRow).filter(OntologyObjectRow.company_id == cid).count()'),
    ('        project_outbox(db, force=True)',
     '        project_outbox(db, force=True, company_id=cid)'),
]
for old, new in pairs:
    if old in t:
        t = t.replace(old, new, 1)
        print("OK:", old[:50])
    else:
        print("MISS:", old[:50])
p.write_text(t, encoding="utf-8")
ast.parse(p.read_text(encoding="utf-8"))
print("SYNTAX OK")