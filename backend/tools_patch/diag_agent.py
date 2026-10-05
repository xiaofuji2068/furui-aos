# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import os
os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios_test"
from app.db import SessionLocal
from app.models_ai import Agent
db = SessionLocal()
q1 = db.query(Agent).filter(Agent.code == "sales-agent").first()
print("filter sales-agent:", getattr(q1, "id", None), getattr(q1, "code", None))
a = db.query(Agent).first()
print("first():", a.id, a.code, a.status)
for r in db.query(Agent).order_by(Agent.id).all():
    print("  ", r.id, r.code, r.status)
db.close()