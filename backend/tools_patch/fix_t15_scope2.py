# -*- coding: utf-8 -*-
from pathlib import Path
T = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tests")
CID = '    cid = getattr(db.query(Company).order_by(Company.id).first(), "id", 1)\n'

# 1) task_state_machine：_run 签名带 question 参数
p = T / "test_task_state_machine.py"
t = p.read_text(encoding="utf-8")
old = 'async def _run(db, agent, user, question="分析本月销售下降原因") -> MainlineRunner:\n    runner = MainlineRunner(db, agent, user, company_id=cid)'
new = 'async def _run(db, agent, user, question="分析本月销售下降原因") -> MainlineRunner:\n' + CID + '    runner = MainlineRunner(db, agent, user, company_id=cid)'
if old in t:
    t = t.replace(old, new, 1)
    p.write_text(t, encoding="utf-8")
    print("task_state_machine: PATCHED")
else:
    print("task_state_machine: MISS")

# 2) outbox：补 import Company
p = T / "test_outbox_projector.py"
t = p.read_text(encoding="utf-8")
old = 'from app.db import SessionLocal  # noqa: E402'
new = 'from app.db import SessionLocal  # noqa: E402\nfrom app.models import Company  # noqa: E402'
if old in t and "from app.models import Company" not in t:
    t = t.replace(old, new, 1)
    p.write_text(t, encoding="utf-8")
    print("outbox: PATCHED")
else:
    print("outbox: SKIP/EXISTS")

# 3) 语法校验
import ast
for f in ("test_task_state_machine.py", "test_outbox_projector.py"):
    ast.parse((T / f).read_text(encoding="utf-8"))
    print(f"{f}: SYNTAX OK")