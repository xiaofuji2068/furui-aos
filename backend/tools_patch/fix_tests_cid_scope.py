# -*- coding: utf-8 -*-
"""修复 cid 作用域/缩进问题（第二轮 patch 引入）。"""
from pathlib import Path
T = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tests")
CID = '    cid = getattr(db.query(Company).order_by(Company.id).first(), "id", 1)\n'

def patch_file(name, pairs):
    p = T / name
    t = p.read_text(encoding="utf-8")
    for old, new in pairs:
        if old in t:
            t = t.replace(old, new, 1)
            print(f"{name}: OK  {old.splitlines()[0][:60]}")
        else:
            print(f"{name}: MISS {old.splitlines()[0][:60]}")
    p.write_text(t, encoding="utf-8")

# 1) 顶层函数内补 cid（mainline / nuclear / task_state_machine）
patch_file("test_mainline.py", [
    ("async def _run(db, agent, user) -> dict:\n    runner = MainlineRunner(db, agent, user, company_id=cid)\n",
     "async def _run(db, agent, user) -> dict:\n" + CID + "    runner = MainlineRunner(db, agent, user, company_id=cid)\n"),
])
patch_file("test_nuclear_scenario.py", [
    ("async def run_inspection(db, agent, user, question=\"8月核电设备巡检异常归因\") -> MainlineRunner:\n    runner = MainlineRunner(db, agent, user, company_id=cid",
     "async def run_inspection(db, agent, user, question=\"8月核电设备巡检异常归因\") -> MainlineRunner:\n" + CID + "    runner = MainlineRunner(db, agent, user, company_id=cid"),
])
patch_file("test_task_state_machine.py", [
    ("async def _run(db, agent, user) -> dict:\n    runner = MainlineRunner(db, agent, user, company_id=cid)\n",
     "async def _run(db, agent, user) -> dict:\n" + CID + "    runner = MainlineRunner(db, agent, user, company_id=cid)\n"),
])

# 2) with 块内缩进修复（eval_contract / receipts / outbox）
for name in ("test_eval_contract.py", "test_receipts.py", "test_outbox_projector.py"):
    p = T / name
    t = p.read_text(encoding="utf-8")
    old = '    cid = getattr(db.query(Company).order_by(Company.id).first(), "id", 1)\n        '
    new = '        cid = getattr(db.query(Company).order_by(Company.id).first(), "id", 1)\n        '
    if old in t:
        t = t.replace(old, new, 1)
        p.write_text(t, encoding="utf-8")
        print(f"{name}: INDENT-FIXED")
    else:
        print(f"{name}: INDENT-MISS")