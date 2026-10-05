"""失败路径验收（TASK-008：每一步都要记录执行状态与错误）。

锁定一条底线：工具调用失败时，任务必须停下来报错，
绝不允许拿着残缺数据继续生成"看起来完整"的分析报告 —— 那比直接失败危险得多。

运行：backend/venv/Scripts/python.exe tests/test_failure_path.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import app.models  # noqa: F401  先注册表，避免外键解析失败
from app.bootstrap import init_all
from app.db import SessionLocal
from app.mainline import MainlineRunner
from app.models import Company, User
from app.models_ai import Agent, AgentStep, AgentTask, DataSource

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  → {detail}" if detail else ""))


def run() -> int:
    db = SessionLocal()
    cid = getattr(db.query(Company).order_by(Company.id).first(), "id", 1)
    original_tables: dict[int, str] = {}

    try:
        init_all()
        sales = db.query(Agent).filter(Agent.code == "sales-analyst").first()
        user = db.query(User).filter(User.username == "sales").first()
        # 修复后 ERP 已默认授权 customers（与 CRM 同库，Agent JOIN 需要）。
        # query_erp_orders 有 extra=("customers",) 跨类别声明，只要任一数据源仍授权 customers
        # 就会放行；因此本测试必须从【全部】数据源临时移除 customers，才能让第 1 步真正失败，
        # 与"第 1 步失败"的断言保持一致。
        # 备份，确保测试结束后还原
        for d in db.query(DataSource).all():
            original_tables[d.id] = d.allowed_tables

        print("\n=== 构造失败：撤销全部数据源的 customers 表授权 ===")
        for d in db.query(DataSource).all():
            tables = json.loads(d.allowed_tables or "[]")
            d.allowed_tables = json.dumps([t for t in tables if t != "customers"])
        db.commit()
        remaining = {
            d.name: json.loads(d.allowed_tables or "[]")
            for d in db.query(DataSource).all()
        }
        check("已撤销全部数据源的 customers 授权",
              all("customers" not in v for v in remaining.values()), str(remaining))

        print("\n=== 执行主线（预期在第 1 步失败）===")
        events = []

        async def go():
            async for ev in MainlineRunner(db, sales, user, company_id=cid).run(
                "分析本月销售下降原因"
            ):
                events.append(ev["event"])

        asyncio.run(go())
        seq = [e for e in events]
        print(f"  事件序列: {seq}")

        check("推送了 error 事件", "error" in seq, str(seq))
        check("推送了 done 事件", "done" in seq)
        check("未推送 token（不应生成报告正文）", "token" not in seq)

        print("\n=== 任务与步骤状态 ===")
        task = db.query(AgentTask).order_by(AgentTask.id.desc()).first()
        check("任务状态为 Failed", task.status == "Failed", task.status)
        check("任务记录了失败原因", "customers" in (task.error or ""), task.error or "")
        check("未生成报告正文", not (task.result or "").strip(),
              f"{len(task.result or '')} 字")

        steps = (
            db.query(AgentStep)
            .filter(AgentStep.task_id == task.id)
            .order_by(AgentStep.seq)
            .all()
        )
        check("第 1 步标记为 Failed", steps[0].status == "Failed", steps[0].status)
        check("第 1 步记录了错误信息", "customers" in (steps[0].error or ""), steps[0].error or "")
        check("后续步骤未继续执行",
              all(s.status == "Pending" for s in steps[1:]),
              str([(s.seq, s.status) for s in steps]))

        print("\n=== Agent 状态 ===")
        db.refresh(sales)
        check("Agent 被置为 Error", sales.status == "Error", sales.status)

    finally:
        print("\n=== 还原授权配置 ===")
        for did, tables in original_tables.items():
            d = db.get(DataSource, did)
            if d:
                d.allowed_tables = tables
        db.commit()
        a = db.query(Agent).filter(Agent.code == "sales-analyst").first()
        if a and a.status == "Error":
            a.status = "Published"
            db.commit()
        for d in db.query(DataSource).all():
            print(f"  {d.category}: {d.allowed_tables}")
        db.close()

    print("\n" + "=" * 56)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        for f in FAIL:
            print(f"  ✗ {f}")
    print("=" * 56)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
