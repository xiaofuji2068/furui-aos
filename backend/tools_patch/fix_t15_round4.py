# -*- coding: utf-8 -*-
from pathlib import Path
import ast
R = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")

# 1) _upsert_db_link：query 前 flush（autoflush=False 下保证同事务幂等）
p = R / "app" / "ontology" / "__init__.py"
t = p.read_text(encoding="utf-8")
old = '''    """按 (type, source_id, target_id) 幂等 upsert 一条关系。"""
    row = (db.query(OntologyLinkRow)'''
new = '''    """按 (type, source_id, target_id) 幂等 upsert 一条关系。"""
    db.flush()  # autoflush=False：先落 pending 再查，保证同事务内幂等（PG 唯一键）
    row = (db.query(OntologyLinkRow)'''
if old in t:
    t = t.replace(old, new, 1)
    p.write_text(t, encoding="utf-8")
    print("ontology/__init__.py: PATCHED")
else:
    print("ontology: MISS")

# 2) outbox 测试：写 link 传 company_id=cid
p = R / "tests" / "test_outbox_projector.py"
t = p.read_text(encoding="utf-8")
old = "            _upsert_db_link(db, link)"
new = "            _upsert_db_link(db, link, company_id=cid)"
if old in t:
    t = t.replace(old, new, 1)
    p.write_text(t, encoding="utf-8")
    print("outbox: PATCHED")
else:
    print("outbox: MISS")

# 3) receipts：agent 查询加 order_by(Agent.id)
p = R / "tests" / "test_receipts.py"
t = p.read_text(encoding="utf-8")
old = 'agent = db.query(Agent).filter(Agent.code == "sales-agent").first() or \\\n            db.query(Agent).first()'
new = 'agent = db.query(Agent).filter(Agent.code == "sales-agent").order_by(Agent.id).first() or \\\n            db.query(Agent).order_by(Agent.id).first()'
if old in t:
    t = t.replace(old, new, 1)
    p.write_text(t, encoding="utf-8")
    print("receipts: PATCHED")
else:
    print("receipts: MISS")

for f in (R/"app"/"ontology"/"__init__.py", R/"tests"/"test_outbox_projector.py", R/"tests"/"test_receipts.py"):
    ast.parse(f.read_text(encoding="utf-8"))
    print(f"{f.name}: SYNTAX OK")