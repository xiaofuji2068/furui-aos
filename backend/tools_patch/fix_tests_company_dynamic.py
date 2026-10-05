# -*- coding: utf-8 -*-
"""批量：测试硬编码 company_id=1 -> 动态 cid（适配 PG id=3/4）。"""
from pathlib import Path
T = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tests")

files = ["test_mainline.py","test_nuclear_scenario.py","test_failure_path.py",
         "test_task_state_machine.py","test_receipts.py","test_eval_contract.py",
         "test_outbox_projector.py","test_auth_rbac.py","test_logic_graph.py"]

CID_LINE = "    cid = getattr(db.query(Company).order_by(Company.id).first(), \"id\", 1)\n"

for name in files:
    p = T / name
    t = p.read_text(encoding="utf-8")
    orig = t
    # 1) import Company
    if "from app.models import Company" not in t:
        if "from app.models import User" in t:
            t = t.replace("from app.models import User", "from app.models import Company, User", 1)
        elif "from app.models import" in t and "Company" not in t.split("\n")[0:60]:
            t = t.replace("from app.models import", "from app.models import Company,", 1)
        else:
            t = t.replace("from app import models  # noqa: F401",
                          "from app import models  # noqa: F401\nfrom app.models import Company", 1)
    # 2) cid 定义（db = SessionLocal() 后）
    anchor = "    db = SessionLocal()\n"
    if anchor in t and "cid = getattr" not in t:
        t = t.replace(anchor, anchor + CID_LINE, 1)
    # 3) 硬编码替换
    t = t.replace("company_id=1", "company_id=cid")
    t = t.replace("company_id == 1", "company_id == cid")
    t = t.replace('"/api/org/departments?company_id=1"', 'f"/api/org/departments?company_id={cid}"')
    # 4) logic_graph 特殊：code==furui -> 动态首企业
    if name == "test_logic_graph.py":
        t = t.replace('db.query(Company).filter(Company.code == "furui").first()',
                      'db.query(Company).order_by(Company.id).first()')
    if t != orig:
        p.write_text(t, encoding="utf-8")
        print(f"{name}: PATCHED")
    else:
        print(f"{name}: NO CHANGE")