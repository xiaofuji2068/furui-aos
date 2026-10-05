# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import os
os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios_test"
from app.db import SessionLocal
from app.models import Company, User
from app.models_ai import Agent, Approval, ApprovalRule
from app.tool_gateway import ToolContext, execute

db = SessionLocal()
cid = db.query(Company).order_by(Company.id).first().id
user = db.query(User).filter(User.username == "admin").first()
agent = db.query(Agent).filter(Agent.code == "sales-analyst").first()
print("cid", cid, "user", user.id if user else None, "agent", agent.code if agent else None, "status", agent.status if agent else None)
cols = [c.name for c in ApprovalRule.__table__.columns]
print("AR cols:", cols)
rules = db.query(ApprovalRule).filter(ApprovalRule.company_id == cid).all()
print("rules count:", len(rules))
for r in rules[:12]:
    print("  rule:", {k: getattr(r, k) for k in cols if k in ("name","action","approval_level","enabled","company_id")})
ctx = ToolContext(db=db, agent=agent, user=user, company_id=cid)
try:
    r3 = execute(ctx, "create_sales_task", {
        "customer_id": 1, "customer_name": "Lineage 测试客户", "title": "Lineage 拒绝测试",
        "detail": "测试", "priority": "medium", "owner": "王销", "due_date": "2026-10-01",
        "_reason": "验收测试", "_evidence": {"qty": 2},
    })
    print("execute ->", str(r3)[:400])
    ap = db.query(Approval).filter(Approval.company_id == cid).order_by(Approval.id.desc()).first()
    print("latest approval:", ap.id if ap else None, getattr(ap, "status", None), getattr(ap, "approval_level", None))
except Exception as e:
    import traceback; traceback.print_exc()