"""TASK-012 长程任务状态机验收测试（图谱 40-06：TaskBrief / Stage / Checkpoint / Review / Return）。

覆盖：
  阶段一 状态机迁移白名单（can_transition / transition）
  阶段二 任务执行后 Brief + Stage + Checkpoint 落库
  阶段三 审批回路驱动状态：approve → Completed；reject → Returned
  阶段四 人工复核 API：InReview → approve / return
  阶段五 Retry 复用：Returned 任务重跑 → 状态回到 Running → 最终 WaitingApproval

运行： backend 目录下  ./venv/Scripts/python.exe tests/test_task_state_machine.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient            # noqa: E402

from app.bootstrap import init_all                    # noqa: E402
from app.db import SessionLocal                       # noqa: E402
from app.main import app as main_app                  # noqa: E402
from app.models import Company, User                           # noqa: E402
from app.models_ai import (                           # noqa: E402
    Agent, AgentStage, AgentTask, Approval, TaskReview, can_transition,
)
from app.mainline import MainlineRunner                # noqa: E402
from app.tool_gateway import decide_approval           # noqa: E402

PASS, FAIL = [], []


def check(name: str, ok: bool, extra: str = "") -> None:
    (PASS if ok else FAIL).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{('  → ' + extra) if extra else ''}")


def login(client: TestClient, username: str) -> dict:
    r = client.post("/api/auth/login", json={"username": username, "password": "123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['token']}"}


async def _run(db, agent, user, question="分析本月销售下降原因") -> MainlineRunner:
    cid = getattr(db.query(Company).order_by(Company.id).first(), "id", 1)
    runner = MainlineRunner(db, agent, user, company_id=cid)
    async for _ in runner.run(question):
        pass
    return runner


def main() -> int:
    init_all()
    db = SessionLocal()
    cid = getattr(db.query(Company).order_by(Company.id).first(), "id", 1)

    print("\n=== 阶段一：状态机迁移白名单 ===")
    check("Pending → Planning 合法", can_transition("Pending", "Planning"))
    check("Planning → Running 合法", can_transition("Planning", "Running"))
    check("Running → WaitingApproval 合法", can_transition("Running", "WaitingApproval"))
    check("Running → InReview 合法", can_transition("Running", "InReview"))
    check("WaitingApproval → InReview 合法", can_transition("WaitingApproval", "InReview"))
    check("WaitingApproval → Returned 合法", can_transition("WaitingApproval", "Returned"))
    check("InReview → Completed 合法", can_transition("InReview", "Completed"))
    check("InReview → Returned 合法", can_transition("InReview", "Returned"))
    check("Returned → Running 合法（可重跑）", can_transition("Returned", "Running"))
    check("Failed → Running 合法（可重试）", can_transition("Failed", "Running"))
    check("Completed → Running 非法", not can_transition("Completed", "Running"))
    check("Pending → Completed 非法（跳过中间态）", not can_transition("Pending", "Completed"))
    check("Unknown → Running 非法", not can_transition("Unknown", "Running"))
    t = AgentTask(company_id=cid, title="x", status="Pending")
    check("transition 非法迁移返回 False 且不改状态",
          t.transition("Completed") is False and t.status == "Pending")
    check("transition 合法迁移生效",
          t.transition("Planning") is True and t.status == "Planning")

    print("\n=== 阶段二：任务执行后 Brief + Stage + Checkpoint 落库 ===")
    agent = db.query(Agent).filter(Agent.code == "sales-analyst").first()
    user = db.query(User).filter(User.username == "sales").first()
    runner = asyncio.run(_run(db, agent, user))
    task: AgentTask = runner.task

    db.refresh(task)
    check("任务状态 WaitingApproval（审批前）", task.status == "WaitingApproval", task.status)
    brief = task.brief_obj
    check("TaskBrief 已写入", bool(brief), str(brief)[:60])
    check("Brief 含 goal", "goal" in brief and "分析" in brief.get("goal", ""))
    check("Brief 含验收标准 acceptance", len(brief.get("acceptance", [])) >= 3,
          f"{len(brief.get('acceptance', []))} 条")
    check("Brief 含约束 constraints", len(brief.get("constraints", [])) >= 2,
          f"{len(brief.get('constraints', []))} 条")

    stages = db.query(AgentStage).filter(AgentStage.task_id == task.id).order_by(AgentStage.seq).all()
    check("创建了 3 个阶段投影", len(stages) == 3, f"{len(stages)} 个")
    if len(stages) == 3:
        names = [s.name for s in stages]
        check("阶段顺序：数据采集→归因分析→行动确认",
              names == ["数据采集", "归因分析", "行动确认"], "/".join(names))
        check("阶段 1（数据采集）已完成", stages[0].status == "Completed", stages[0].status)
        check("阶段 1 含 checkpoint", bool(stages[0].checkpoint),
              stages[0].checkpoint[:80])
        cp1 = stages[0].checkpoint_obj
        check("checkpoint 含 ERP 摘要", any("订单" in str(v) for v in cp1.values()), str(cp1)[:80])
        check("阶段 2（归因分析）已完成", stages[1].status == "Completed", stages[1].status)
        cp2 = stages[1].checkpoint_obj
        check("checkpoint 含头号下滑客户", "top_drop_customer" in cp2,
              str(cp2.get("top_drop_customer", ""))[:60])
        check("阶段 3（行动确认）已完成", stages[2].status == "Completed", stages[2].status)
        cp3 = stages[2].checkpoint_obj
        check("checkpoint 含审批单 id", "approval_id" in cp3, str(cp3)[:80])

    print("\n=== 阶段三：审批回路驱动任务状态 ===")
    ap = db.query(Approval).filter(Approval.task_id == task.id).first()
    check("存在待审批单", ap is not None and ap.status == "Pending",
          f"approval#{ap.id if ap else '-'}")

    # --- 3a：reject → 任务 Returned ---
    task2_runner = asyncio.run(_run(db, agent, user))
    task2 = task2_runner.task
    db.refresh(task2)
    ap2 = db.query(Approval).filter(Approval.task_id == task2.id).first()
    owner = db.query(User).filter(User.username == "sales").first()
    if ap2:
        r = decide_approval(db, ap2.id, user=owner, decision="reject", comment="数据口径存疑，请补充")
        db.refresh(task2)
        check("审批拒绝成功", r.get("ok") and r.get("status") == "Rejected", str(r.get("error", "")))
        check("任务随审批拒绝回到 Returned", task2.status == "Returned", task2.status)
        check("Returned 任务记录退回原因", "存疑" in (task2.error or ""), task2.error or "")

    # --- 3b：approve → 任务 Completed ---
    if ap:
        r = decide_approval(db, ap.id, user=owner, decision="approve", comment="同意，按二级响应执行")
        db.refresh(task)
        check("审批批准成功", r.get("ok") and r.get("status") == "Executed", str(r.get("error", "")))
        check("任务随审批批准转为 Completed", task.status == "Completed", task.status)
        check("Completed 任务记录了完成时间", task.finished_at is not None)

    print("\n=== 阶段四：人工复核 API（InReview → approve / return）===")
    with TestClient(main_app) as client:
        h = login(client, "sales")
        # 构造一个 InReview 任务（从 Completed 派生一个新任务走 API 全链路太重，直接跑 runner 到 Completed 后置 InReview）
        runner3 = asyncio.run(_run(db, agent, user))
        t3 = runner3.task
        db.refresh(t3)
        # 置为 InReview（由 API review 端点支持的状态入口：直接迁移）
        check("InReview 前置迁移合法", t3.transition("InReview"), t3.status)
        db.commit()

        r = client.post(f"/api/tasks/{t3.id}/review",
                        json={"decision": "approve", "comment": "复核通过"}, headers=h)
        check("review approve 返回 200", r.status_code == 200, r.text[:120])
        d = r.json().get("data", {})
        check("review approve 后任务 Completed", d.get("status") == "Completed", str(d.get("status")))

        rv = db.query(TaskReview).filter(TaskReview.task_id == t3.id).all()
        check("复核记录已落库", len(rv) == 1, f"{len(rv)} 条")
        if rv:
            check("复核记录含复核人与意见",
                  rv[0].reviewer_name == "李明" and rv[0].decision == "approve",
                  f"{rv[0].reviewer_name} / {rv[0].decision}")

        # return 分支：新任务置 InReview → return
        runner4 = asyncio.run(_run(db, agent, user))
        t4 = runner4.task
        db.refresh(t4)
        t4.transition("InReview")
        db.commit()
        r = client.post(f"/api/tasks/{t4.id}/review",
                        json={"decision": "return", "comment": "报告缺少次因分析"}, headers=h)
        check("review return 返回 200", r.status_code == 200, r.text[:120])
        db.refresh(t4)
        check("review return 后任务 Returned", t4.status == "Returned", t4.status)
        check("Returned 任务记录退回意见", "次因" in (t4.error or ""), t4.error or "")

        # 无审批权限者（analyst）复核被拒
        h_analyst = login(client, "analyst")
        runner5 = asyncio.run(_run(db, agent, user))
        t5 = runner5.task
        db.refresh(t5)
        t5.transition("InReview")
        db.commit()
        r = client.post(f"/api/tasks/{t5.id}/review",
                        json={"decision": "approve"}, headers=h_analyst)
        check("无复核权限者被拒(403)", r.status_code == 403, str(r.status_code))

    print("\n=== 阶段五：Retry 复用（Returned 任务重跑）===")
    with TestClient(main_app) as client:
        h = login(client, "sales")
        # 用上面 Returned 的 t4 重跑（走 API SSE 完整链路）
        with client.stream("POST", f"/api/tasks/{t4.id}/retry",
                           json={"question": t4.input_text, "agent_code": "sales-analyst"},
                           headers=h) as resp:
            body = "".join(resp.iter_text())
        check("retry SSE 返回 200", resp.status_code == 200, str(resp.status_code))
        check("retry 流含 task/step/done 事件",
              "event: task" in body and "event: step" in body and "event: done" in body,
              f"{len(body)} 字符")
        db.refresh(t4)
        check("retry 后任务回到执行态（WaitingApproval 或 Completed）",
              t4.status in ("WaitingApproval", "Completed"), t4.status)
        check("retry 后任务重跑计数 +1", t4.retry_count >= 1, f"retry_count={t4.retry_count}")
        new_stages = db.query(AgentStage).filter(AgentStage.task_id == t4.id).count()
        check("retry 后阶段投影重建", new_stages == 3, f"{new_stages} 个")
        from app.models_ai import AgentExecution
        exec_cnt = db.query(AgentExecution).filter(AgentExecution.task_id == t4.id).count()
        check("retry 后执行日志重新生成", exec_cnt >= 5, f"{exec_cnt} 条")

    # ---- 收尾：恢复任务终态（保持数据库干净）----
    for tt in (task, task2, t3, t4, t5):
        try:
            db.refresh(tt)
        except Exception:                                  # noqa: BLE001
            continue
        if tt.status in ("WaitingApproval", "InReview", "Returned", "Failed"):
            tt.status = "Completed"
            tt.finished_at = None
    db.commit()
    db.close()

    print("\n" + "=" * 56)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        print("\n失败项：")
        for f in FAIL:
            print("  -", f)
    print("=" * 56)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
