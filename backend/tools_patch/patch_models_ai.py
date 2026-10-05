# -*- coding: utf-8 -*-
"""TASK-002 模型层补丁：models_ai.py 新增 InspectionWorkOrder（核电巡检工单）。"""
P = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\models_ai.py"
with open(P, "r", encoding="utf-8") as f:
    src = f.read()

anchor = "class SalesTask(Base):"
new_model = '''class InspectionWorkOrder(Base):
    """核电巡检工单 — Agent 经人工审批后创建的巡检处置动作落点。

    与 SalesTask 同构但独立建表：业务语境不同（巡检处置 vs 销售跟进），
    生命周期、责任人、审批链路各自独立，避免跨领域概念污染。
    """
    __tablename__ = "inspection_work_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    station_code: Mapped[str] = mapped_column(String(32), default="")   # MS-01 等
    station_name: Mapped[str] = mapped_column(String(120), default="")

    title: Mapped[str] = mapped_column(String(200), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(20), default="high")   # high/medium/low
    owner: Mapped[str] = mapped_column(String(64), default="")
    due_date: Mapped[str] = mapped_column(String(20), default="")
    status: Mapped[str] = mapped_column(String(20), default="待处置")

    source: Mapped[str] = mapped_column(String(20), default="agent")    # agent / human
    agent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approval_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))


'''
assert anchor in src, "SalesTask anchor missing"
src = src.replace(anchor, new_model + anchor, 1)
with open(P, "w", encoding="utf-8") as f:
    f.write(src)
print("MODEL PATCH OK")
