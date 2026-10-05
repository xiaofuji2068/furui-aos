# -*- coding: utf-8 -*-
"""TASK-002 核电巡检场景验收测试（图 40-13）。
覆盖：
  阶段一 巡检主线 6 步执行（监测站→指标→知识→归因→报告→工单审批）
  阶段二 审批通过 → 工单落库（InspectionWorkOrder）+ 任务 Completed
  阶段三 审批拒绝 → 工单不创建 + 任务 Returned
  阶段四 本体图核电实体（监测站/区域/指标/巡检记录/工单关联）

运行：backend 目录下 ./venv/Scripts/python.exe tests/test_nuclear_scenario.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["ENABLE_REAL_LLM"] = "false"  # 离线规则化报告，避免外呼 LLM

from app.bootstrap import init_all                            # noqa: E402
from app.db import SessionLocal                               # noqa: E402
from app.models import Company, User                          # noqa: E402
from app.models_ai import (                                   # noqa: E402
    Agent, AgentTask, Approval, InspectionWorkOrder,
)
from app.mainline import MainlineRunner                        # noqa: E402
from app.tool_gateway import decide_approval                   # noqa: E402
from app.ontology import build_demo_ontology                   # noqa: E402

PASS, FAIL = [], []


def check(name: str, ok: bool, extra: str = "") -> None:
    (PASS if ok else FAIL).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{('   -> ' + extra) if extra else ''}")


async def run_inspection(db, agent, user, question="8月核电设备巡检异常归因") -> MainlineRunner:
    cid = getattr(db.query(Company).order_by(Company.id).first(), "id", 1)
    runner = MainlineRunner(db, agent, user, company_id=cid, conversation_id="C-TEST-NUCLEAR")
    async for _ in runner.run(question):
        pass
    return runner


def main() -> int:
    init_all()
    db = SessionLocal()
    cid = getattr(db.query(Company).order_by(Company.id).first(), "id", 1)

    company = db.query(Company).filter(Company.code == "FURUI").first()
    cid = company.id if company else 1
    agent = db.query(Agent).filter(Agent.code == "inspection-analyst").first()
    user = db.query(User).filter(User.company_id == cid).first()
    assert agent and user, "巡检 Agent / 用户缺失"

    print("\n=== 阶段一：巡检主线 6 步 ===")
    check("巡检 Agent 存在且已发布", agent.status == "Published", agent.status)
    check("Agent 已挂 5 个能力（4 工具 + 知识 + 建单）",
          len(agent.skills) >= 5, f"{len(agent.skills)} 个")

    runner = asyncio.run(run_inspection(db, agent, user))
    task: AgentTask = runner.task
    db.refresh(task)

    check("任务已创建", task.id is not None, f"id={task.id}")
    from app.models_ai import AgentStep
    steps = db.query(AgentStep).filter(AgentStep.task_id == task.id).order_by(AgentStep.seq).all()
    check("计划 6 步", len(steps) == 6, f"{len(steps)} 步")
    check("计划含建单步骤", any("工单" in s.title for s in steps), "/".join(s.title for s in steps))
    check("任务等待审批（工单 Level 3）", task.status == "WaitingApproval", task.status)

    from app.models_ai import AgentExecution
    execs = db.query(AgentExecution).filter(AgentExecution.task_id == task.id).all()
    executed = [e.tool_name for e in execs if e.tool_name]
    print(f"    执行日志工具: {executed}")
    check("巡检工具已执行", "query_monitoring_stations" in executed and "analyze_inspection_anomaly" in executed,
          "/".join(executed[:8]) if executed else "无")

    from app.models_ai import AgentStage
    stages = db.query(AgentStage).filter(AgentStage.task_id == task.id).order_by(AgentStage.seq).all()
    check("阶段投影已建", len(stages) == 3, f"{len(stages)} 个")

    print("\n=== 阶段二：审批通过 → 工单落库 ===")
    ap = db.query(Approval).filter(
        Approval.company_id == cid, Approval.action == "create_workorder",
        Approval.status == "Pending",
    ).order_by(Approval.id.desc()).first()
    check("存在待审批工单", bool(ap), f"approval#{ap.id if ap else '-'}")

    wo_before = db.query(InspectionWorkOrder).count()
    r_ok = False
    if ap:
        r = decide_approval(db, ap.id, user=user, decision="approved", comment="验收通过")
        r_ok = bool(r.get("ok")) and r.get("status") == "Executed"
    check("审批通过执行成功", r_ok, str(r if ap else ""))
    wo_after = db.query(InspectionWorkOrder).count()
    check("工单已落库", wo_after == wo_before + 1, f"{wo_before} -> {wo_after}")
    wo = db.query(InspectionWorkOrder).order_by(InspectionWorkOrder.id.desc()).first()
    if wo:
        check("工单字段完整", wo.station_code and wo.title and wo.priority and wo.owner,
              f"{wo.station_code} {wo.title} priority={wo.priority}")
        check("工单关联审批", wo.approval_id == ap.id, f"approval_id={wo.approval_id}")

    print("\n=== 阶段三：审批拒绝 → 工单不创建 + 任务回退 ===")
    # 自跑一条新主线产生独立审批，避免复用阶段二已消费的审批
    runner2 = asyncio.run(run_inspection(
        db, agent, user, question="8月核电设备巡检异常归因（拒绝路径）"))
    task2: AgentTask = runner2.task
    db.refresh(task2)
    ap2 = db.query(Approval).filter(
        Approval.company_id == cid, Approval.action == "create_workorder",
        Approval.status == "Pending",
    ).order_by(Approval.id.desc()).first()
    wo_before2 = db.query(InspectionWorkOrder).count()
    r_rej = False
    if ap2:
        rr = decide_approval(db, ap2.id, user=user, decision="reject", comment="验收拒绝")
        r_rej = bool(rr.get("ok")) and rr.get("status") == "Rejected"
    check("审批拒绝成功", r_rej, str(rr if ap2 else "无待审工单"))
    wo_after2 = db.query(InspectionWorkOrder).count()
    check("拒绝后未创建工单", wo_after2 == wo_before2, f"{wo_before2} -> {wo_after2}")
    if ap2 and ap2.task_id:
        t2 = db.query(AgentTask).filter(AgentTask.id == ap2.task_id).first()
        check("关联任务回退 Returned", t2.status == "Returned", t2.status)

    print("\n=== 阶段四：本体图核电实体 ===")
    g = build_demo_ontology()
    ts = g["types"]
    check("监测站 5 个", len(ts["MonitoringStation"].list()) == 5)
    check("区域 3 个", len(ts["Area"].list()) == 3)
    check("指标记录 5 条", len(ts["MetricRecord"].list()) == 5)
    check("巡检记录 5 条", len(ts["InspectionRecord"].list()) == 5)
    check("工单含巡检单", any(o.properties.get("station_code") for o in ts["WorkOrder"].list()))
    check("巡检归因 Function 已注册",
          any(f.name == "analyze_inspection_anomaly" for f in g["functions"]))
    check("对象关联完整", len(g["links"]) >= 30, f"{len(g['links'])} 条")

    db.close()
    print(f"\n========== RESULT: {len(PASS)} PASS / {len(FAIL)} FAIL ==========")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
