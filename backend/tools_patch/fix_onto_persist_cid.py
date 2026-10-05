# -*- coding: utf-8 -*-
from pathlib import Path
import ast
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tests\test_ontology_persistence.py")
t = p.read_text(encoding="utf-8")
reps = [
    ("from app.models_ontology import (  # noqa: E402",
     "from app.models import Company  # noqa: E402\nfrom app.models_ontology import (  # noqa: E402"),
    ("        db = SessionLocal()\n        try:",
     "        db = SessionLocal()\n        cid = db.query(Company).order_by(Company.id).first().id\n        try:"),
    # 所有 filter_by(type= → 带 company
    ("filter_by(type=", "filter_by(company_id=cid, type="),
    # WorkOrder 种子查询
    ('.filter(OntologyObjectRow.type == "WorkOrder",',
     '.filter(OntologyObjectRow.company_id == cid, OntologyObjectRow.type == "WorkOrder",'),
    # 全量 count → 带 company
    ("before = db.query(OntologyObjectRow).count()",
     "before = db.query(OntologyObjectRow).filter(OntologyObjectRow.company_id == cid).count()"),
    ("after = db.query(OntologyObjectRow).count()",
     "after = db.query(OntologyObjectRow).filter(OntologyObjectRow.company_id == cid).count()"),
    ("n_link = db.query(OntologyLinkRow).count()",
     "n_link = db.query(OntologyLinkRow).filter(OntologyLinkRow.company_id == cid).count()"),
    ("link_ids = {(r.type, r.source_id, r.target_id) for r in db.query(OntologyLinkRow).all()}",
     "link_ids = {(r.type, r.source_id, r.target_id) for r in db.query(OntologyLinkRow).filter(OntologyLinkRow.company_id == cid).all()}"),
    ("before_links = db.query(OntologyLinkRow).count()",
     "before_links = db.query(OntologyLinkRow).filter(OntologyLinkRow.company_id == cid).count()"),
    ("after_links = db.query(OntologyLinkRow).count()",
     "after_links = db.query(OntologyLinkRow).filter(OntologyLinkRow.company_id == cid).count()"),
    ("baseline_revs = {r.revision for r in db.query(OntologySchemaRevision).all()}",
     "baseline_revs = {r.revision for r in db.query(OntologySchemaRevision).filter(OntologySchemaRevision.company_id == cid).all()}"),
    ("revs_now = sorted(r.revision for r in db.query(OntologySchemaRevision).all())",
     "revs_now = sorted(r.revision for r in db.query(OntologySchemaRevision).filter(OntologySchemaRevision.company_id == cid).all())"),
    ("n_rev = db.query(OntologySchemaRevision).count()",
     "n_rev = db.query(OntologySchemaRevision).filter(OntologySchemaRevision.company_id == cid).count()"),
    ("for r in db.query(OntologySchemaRevision).all():\n                if r.revision not in baseline_revs:",
     "for r in db.query(OntologySchemaRevision).filter(OntologySchemaRevision.company_id == cid).all():\n                if r.revision not in baseline_revs:"),
    ("seed_ontology(db)", "seed_ontology(db, company_id=cid)"),
    ('bump_revision(db, "test bump")', 'bump_revision(db, "test bump", company_id=cid)'),
    ('bump_revision(db, "test bump 2")', 'bump_revision(db, "test bump 2", company_id=cid)'),
]
n = 0
for o, nw in reps:
    if o in t:
        t = t.replace(o, nw, 1 if o.count("(") else -1)
        n += 1
    else:
        print("MISS:", o[:55])
p.write_text(t, encoding="utf-8")
ast.parse(p.read_text(encoding="utf-8"))
print("PATCHED", n, "SYNTAX OK")