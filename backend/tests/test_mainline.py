"""主线验收测试：清单「第一版必须跑通的完整测试案例」。

用户：分析本月销售下降原因
→ AI 工作台创建任务 → 调用销售分析 Agent → Agent 制定计划
→ 查 ERP → 查 CRM → 查企业知识 → Agent 分析 → 生成销售下降原因
→ 提出建议 → 用户确认：生成销售任务 → Agent 调用 CRM → 创建销售任务
→ 记录日志 → 返回结果 → Dashboard 更新 → 任务完成

运行： backend 目录下  ./venv/Scripts/python.exe tests/test_mainline.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.bootstrap import init_all                      # noqa: E402
from app.db import SessionLocal                          # noqa: E402
from app.models import Company, User                              # noqa: E402
from app.models_ai import (                              # noqa: E402
    ActionReceipt, Agent, AgentExecution, AgentStep, AgentTask, Approval,
    AuditLog, KnowledgeChunk, SalesTask, ToolExecution,
)
from app.mainline import MainlineRunner                  # noqa: E402
from app.tool_gateway import ToolContext, execute, decide_approval  # noqa: E402

PASS, FAIL = [], []


def check(name: str, ok: bool, extra: str = "") -> None:
    (PASS if ok else FAIL).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{('  → ' + extra) if extra else ''}")


async def _run(db, agent, user) -> dict:
    cid = getattr(db.query(Company).order_by(Company.id).first(), "id", 1)
    runner = MainlineRunner(db, agent, user, company_id=cid)
    events = []
    async for ev in runner.run("分析本月销售下降原因"):
        events.append(ev)
    return {"runner": runner, "events": events}


def main() -> int:
    init_all()
    db = SessionLocal()
    cid = getattr(db.query(Company).order_by(Company.id).first(), "id", 1)

    agent = db.query(Agent).filter(Agent.code == "sales-analyst").first()
    user = db.query(User).filter(User.username == "sales").first()

    print("\n=== 阶段一：Agent 执行主线任务 ===")
    res = asyncio.run(_run(db, agent, user))
    events = res["events"]
    task: AgentTask = res["runner"].task

    kinds = [e["event"] for e in events]
    check("产出 task 事件（任务已持久化）", "task" in kinds, f"task_id={task.id}")
    check("产出 6 个步骤事件", sum(1 for e in events if e["event"] == "step") == 12,
          f"step 事件 {sum(1 for e in events if e['event']=='step')} 个（6步×开始/完成）")
    check("产出流式 token（报告正文）", kinds.count("token") > 200, f"{kinds.count('token')} 个 token")
    check("产出 pending 事件（待人工确认）", "pending" in kinds)

    db.refresh(task)
    check("任务落库且状态为 WaitingApproval", task.status == "WaitingApproval", task.status)
    check("任务已绑定 Agent", task.agent_id == agent.id)
    check("步骤全部落库", len(task.steps) == 6, f"{len(task.steps)} 步")
    check("每一步都有执行日志", db.query(AgentExecution)
          .filter(AgentExecution.task_id == task.id).count() >= 5,
          f"{db.query(AgentExecution).filter(AgentExecution.task_id==task.id).count()} 条")

    print("\n=== 阶段二：检索与工具调用真实发生 ===")
    te = db.query(ToolExecution).filter(ToolExecution.task_id == task.id).all()
    names = sorted({t.tool_name for t in te})
    check("调用了 ERP 查询", "query_erp_orders" in names)
    check("调用了 CRM 查询", "query_crm_customers" in names)
    check("调用了知识检索", "search_knowledge" in names)
    check("归因分析已执行", "analyze_sales_drop" in names)
    check("所有调用均记录状态与耗时", all(t.status and t.duration_ms >= 0 for t in te),
          f"{len(te)} 次调用")

    print("\n=== 阶段三：报告内容基于真实数据 ===")
    report = task.result or ""
    check("报告不为空", len(report) > 300, f"{len(report)} 字")
    # 降幅不硬编码：重新取一次真实分析结果再比对，避免样例数据调整后期望值过期
    ctx0 = ToolContext(db=db, agent=agent, user=user, company_id=cid)
    fresh = execute(ctx0, "analyze_sales_drop", {}).get("result", {})
    pct = str((fresh.get("overview") or {}).get("pct"))
    d_amt = str((fresh.get("overview") or {}).get("delta_amt_wan"))
    check("报告含真实环比降幅", bool(pct) and pct in report, f"{pct}%")
    check("报告含真实减少金额", bool(d_amt) and d_amt in report, f"{d_amt} 万元")
    check("报告定位到头号下滑客户", "恒力重工" in report)
    check("报告命中知识库归因规则", "大客户因素" in report)
    check("报告含知识来源引用", "知识来源" in report)

    print("\n=== 阶段四：人工审批回路 ===")
    ap = db.query(Approval).filter(Approval.task_id == task.id).first()
    check("生成了待审批单", ap is not None and ap.status == "Pending",
          f"approval#{ap.id if ap else '-'}")
    if ap:
        check("审批单含 AI 理由", bool(ap.ai_reason))
        check("审批单含数据依据", ap.data_evidence not in ("", "{}"))
        check("审批单含执行计划", ap.plan not in ("", "{}"))

        # analyst 角色只有 approval:view，没有 approval:approve —— 真正的无审批权用户
        analyst = db.query(User).filter(User.username == "analyst").first()
        r = decide_approval(db, ap.id, user=analyst, decision="approve")
        check("无审批权限者被拒绝", (not r.get("ok")) and "审批权限" in r.get("error", ""),
              r.get("error", ""))

        # 有审批权限者批准后真正执行
        owner = db.query(User).filter(User.username == "sales").first()
        r = decide_approval(db, ap.id, user=owner, decision="approve",
                            comment="同意，按二级响应执行")
        check("有权限者批准成功", r.get("ok") and r.get("status") == "Executed", str(r.get("error", "")))

        st = db.query(SalesTask).filter(SalesTask.approval_id == ap.id).first()
        check("销售跟进任务已写入 CRM", st is not None,
              f"#{st.id} {st.title}" if st else "")
        if st:
            check("任务责任人与期限完整", bool(st.owner and st.due_date), f"{st.owner} / {st.due_date}")
            check("任务来源标记为 agent", st.source == "agent")

        # 步骤 2.3：ActionReceipt 动作凭证（审批批准执行路径）
        rcpts = db.query(ActionReceipt).filter(ActionReceipt.approval_id == ap.id).all()
        check("审批执行后生成 ActionReceipt", len(rcpts) == 1, f"{len(rcpts)} 条")
        if rcpts:
            check("Receipt 含参数哈希", bool(rcpts[0].params_hash), rcpts[0].params_hash[:12])
            check("Receipt 含结果哈希", bool(rcpts[0].result_hash), rcpts[0].result_hash[:12])
            check("Receipt 关联审批单", rcpts[0].approval_id == ap.id)

    print("\n=== 阶段四末：Receipt 覆盖 Level2 直行（步骤 2.3）===")
    before = db.query(ActionReceipt).count()
    r2 = execute(ctx0, "analyze_sales_drop", {})
    after = db.query(ActionReceipt).count()
    check("Level2 直行成功", r2.get("ok"), str(r2.get("error", "")))
    check("Level2 执行生成新 Receipt（旧的不变）", after == before + 1, f"{before}->{after}")

    print("\n=== 阶段五：越权与网关拦截 ===")
    kbot = db.query(Agent).filter(Agent.code == "knowledge-assistant").first()
    ctx = ToolContext(db=db, agent=kbot, user=user, company_id=cid)
    r = execute(ctx, "analyze_sales_drop", {})
    check("未授权 Agent 调用分析工具被拦截", not r.get("ok"), r.get("error", ""))
    r = execute(ctx, "query_erp_orders", {})
    check("未授权 Agent 查 ERP 被拦截", not r.get("ok"), r.get("error", ""))

    print("\n=== 阶段六：审计与指标 ===")
    db.refresh(agent)
    check("审计日志已记录", db.query(AuditLog).filter(AuditLog.company_id == cid).count() >= 4,
          f"{db.query(AuditLog).filter(AuditLog.company_id==1).count()} 条")
    check("Agent 任务计数已更新", agent.total_tasks >= 1, f"total={agent.total_tasks}")
    check("知识分片已向量化", db.query(KnowledgeChunk)
          .filter(KnowledgeChunk.embedding.isnot(None)).count() > 0,
          f"{db.query(KnowledgeChunk).filter(KnowledgeChunk.embedding.isnot(None)).count()} 片")

    # ---- 收尾：恢复任务终态 ----
    if task.status == "WaitingApproval":
        task.status = "Completed"
        task.finished_at = None
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
