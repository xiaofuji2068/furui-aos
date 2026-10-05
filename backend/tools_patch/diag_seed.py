# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import os
os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios_test"
from app.db import SessionLocal
from app.models import Company
from app.models_ontology import OntologyObjectRow
from app.ontology import seed_ontology

db = SessionLocal()
cid = db.query(Company).order_by(Company.id).first().id
print("cid:", cid)
print("before:", db.query(OntologyObjectRow).filter(OntologyObjectRow.company_id == cid).count())
seed_ontology(db, company_id=cid)
print("after1:", db.query(OntologyObjectRow).filter(OntologyObjectRow.company_id == cid).count())
seed_ontology(db, company_id=cid)
print("after2:", db.query(OntologyObjectRow).filter(OntologyObjectRow.company_id == cid).count())
row = db.query(OntologyObjectRow).filter_by(company_id=cid, type="Customer", object_id="CUS-001").first()
print("CUS-001 row:", row.id if row else None)
db.close()