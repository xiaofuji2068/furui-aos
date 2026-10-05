"""企业总览（TASK-031 ~ TASK-034）。

    GET /api/overview   KPI / AI 洞察 / 数据源连接状态 —— 全部来自真实数据

设计取舍：
- 清单把「AI 主动洞察」列为第一版暂不做，所以这里不编造"华东区域下降 18%"之类的结论。
  洞察卡片改为由真实运行信号生成：待审批、失败任务、连接异常、近期完成量。
  每一条都能点进去看到对应数据，宁可少而真，不要多而假。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import Company, User
from ..models_ai import Agent, AgentExecution, AgentTask, Approval, DataSource

router = APIRouter(prefix="", tags=["企业总览"])

# 数据源类别 → 图标与色调（展示层，状态本身来自真实表）
SOURCE_STYLE = {
    "ERP": ("🗄", "blue"),
    "CRM": ("👥", "violet"),
    "MES": ("🏭", "amber"),
    "OA": ("📄", "cyan"),
    "IoT": ("📡", "emerald"),
    "业务系统": ("🧩", "slate"),
}


def _greeting(user: User, company: Company | None) -> str:
    hour = datetime.utcnow().hour + 8          # 服务按 UTC 存储，展示按北京时间
    hour = hour % 24
    if 5 <= hour < 11:
        prefix = "早上好"
    elif 11 <= hour < 14:
        prefix = "中午好"
    elif 14 <= hour < 18:
        prefix = "下午好"
    else:
        prefix = "晚上好"
    name = company.name if company else (user.name or "企业用户")
    return f"{prefix}，{name}"


@router.get("/overview")
def overview(user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    cid = user.company_id
    company = db.get(Company, cid) if cid else None

    # ---- KPI：真实统计 ----
    agents = db.query(Agent).filter(Agent.company_id == cid).all() if cid else []
    total_agents = len(agents)
    working_agents = sum(1 for a in agents if a.status == "Running")

    tasks_q = db.query(AgentTask)
    if cid:
        tasks_q = tasks_q.filter(AgentTask.company_id == cid)
    tasks = tasks_q.all()

    # 待确认 = 任务停在等待审批 + 审批单仍挂起
    waiting_tasks = sum(1 for t in tasks if t.status == "WaitingApproval")
    ap_q = db.query(Approval).filter(Approval.status == "Pending")
    if cid:
        ap_q = ap_q.filter(Approval.company_id == cid)
    pending_approvals = ap_q.count()
    tasks_pending = waiting_tasks + pending_approvals

    tasks_completed = sum(1 for t in tasks if t.status == "Completed")
    tasks_failed = sum(1 for t in tasks if t.status == "Failed")

    # 环比：近 7 天 vs 前 7 天
    now = datetime.utcnow()
    d7, d14 = now - timedelta(days=7), now - timedelta(days=14)

    def in_window(t, start, end):
        return t.created_at and start <= t.created_at <= end

    recent_done = sum(1 for t in tasks
                      if t.status == "Completed" and in_window(t, d7, now))
    prev_done = sum(1 for t in tasks
                    if t.status == "Completed" and in_window(t, d14, d7))

    kpis = {
        "ai_employees_total": {"value": total_agents, "delta": 0, "label": "AI 员工总数"},
        "ai_employees_working": {"value": working_agents, "delta": 0, "label": "正在工作"},
        "tasks_pending": {
            "value": tasks_pending,
            "delta": -pending_approvals if pending_approvals else 0,
            "label": "待确认任务",
        },
        "tasks_completed": {
            "value": tasks_completed,
            "delta": recent_done - prev_done,
            "label": "已完成任务（近 7 天 +" + str(recent_done) + "）",
        },
    }

    # ---- 数据源连接状态：来自真实表 ----
    ds_q = db.query(DataSource)
    if cid:
        ds_q = ds_q.filter(DataSource.company_id == cid)
    sources: List[Dict[str, Any]] = []
    for s in ds_q.all():
        icon, tone = SOURCE_STYLE.get(s.category, ("🧩", "slate"))
        status = "connected" if s.status == "Connected" else (
            "warning" if s.status == "Syncing" else "error"
        )
        state = {"Connected": "正常", "Syncing": "同步中",
                 "Disconnected": "未连接", "Error": "异常"}.get(s.status, s.status)
        sources.append({
            "id": str(s.id), "name": s.name, "icon": icon, "tone": tone,
            "status": status, "state": state,
        })
    # 企业知识库单独列一张（它是最重要的数据源，值得在首页可见）
    from ..models_ai import KnowledgeDocument             # 局部导入，避免循环
    kb_q = db.query(KnowledgeDocument)
    if cid:
        kb_q = kb_q.filter(KnowledgeDocument.company_id == cid)
    kb_count = kb_q.count()
    sources.append({
        "id": "kb", "name": "企业知识库", "icon": "📚", "tone": "violet",
        "status": "connected" if kb_count else "warning",
        "state": f"{kb_count} 份文档" if kb_count else "暂无文档",
    })
    sources.append({"id": "__add__", "name": "添加数据源", "icon": "+",
                    "tone": "slate", "status": "add", "state": ""})

    # ---- 洞察：由真实运行信号生成，不编造业务结论 ----
    insights: List[Dict[str, Any]] = []

    if pending_approvals:
        insights.append({
            "id": "APV-PENDING", "type": "warning", "title": "待人工确认",
            "summary": f"{pending_approvals} 项 AI 动作等待你确认",
            "detail": "Agent 在人工批准前不会写入任何业务数据",
            "action": "去审批",
        })

    if tasks_failed:
        insights.append({
            "id": "TASK-FAILED", "type": "danger", "title": "任务失败",
            "summary": f"{tasks_failed} 个任务执行失败",
            "detail": "失败任务不会生成分析报告，可在任务中心查看原因",
            "action": "查看任务",
        })

    err_sources = [s for s in sources if s.get("status") == "error"]
    if err_sources:
        insights.append({
            "id": "DS-ERROR", "type": "danger", "title": "数据连接异常",
            "summary": f"{len(err_sources)} 个数据源连接异常",
            "detail": "、".join(s["name"] for s in err_sources[:3]),
            "action": "检查连接",
        })

    if recent_done:
        insights.append({
            "id": "TASK-DONE", "type": "success", "title": "AI 已完成",
            "summary": f"近 7 天 AI 完成 {recent_done} 项任务",
            "detail": f"前一周期 {prev_done} 项，{'上升' if recent_done >= prev_done else '下降'} "
                      f"{abs(recent_done - prev_done)} 项",
            "action": "查看详情",
        })

    if not insights:
        insights.append({
            "id": "NO-SIGNAL", "type": "primary", "title": "运行平稳",
            "summary": "暂无待处理事项",
            "detail": "AI 主动洞察将在后续版本启用；当前所有数据均为真实运行统计",
            "action": "前往工作台",
        })

    return {
        "greeting": _greeting(user, company),
        "subtitle": "企业智能助手正在为您和您的团队工作",
        "kpis": kpis,
        "insights": insights,
        "data_sources": sources,
        "user": {
            "name": user.name,
            "role": user.roles[0].name if user.roles else "—",
            "company": company.name if company else "",
        },
    }


# Agent 状态 → 前端 WorkingAgents 使用的语义值
_STATUS_MAP = {
    "Running": "working", "Idle": "idle", "WaitingApproval": "waiting",
    "Error": "error", "Paused": "idle", "Published": "idle",
    "Draft": "idle", "Testing": "idle", "Archived": "idle",
}


@router.get("/agents")
def working_agents(user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """AI 员工状态（TASK-033）— 来自真实 Agent 表。"""
    q = db.query(Agent)
    if user.company_id:
        q = q.filter(Agent.company_id == user.company_id)
    rows = q.all()

    items = []
    for a in rows:
        # 当前任务：取该 Agent 最近一条未结束的任务
        t = (db.query(AgentTask)
             .filter(AgentTask.agent_id == a.id,
                     AgentTask.status.in_(("Running", "Pending", "WaitingApproval")))
             .order_by(AgentTask.id.desc()).first())
        items.append({
            "id": a.id,
            "name": a.name,
            "role": a.position or a.agent_type or "",
            "avatar": a.avatar or "🤖",
            "color": "from-violet-500/40 to-blue-500/30",
            "status": _STATUS_MAP.get(a.status, "idle"),
            "current_task": t.title if t else "空闲中",
            "progress": t.progress if t else 0,
            "skills": [],
            "today_tasks": a.today_tasks or 0,
            "success_tasks": a.success_tasks or 0,
        })
    return {"items": items}


@router.get("/activities")
def recent_activities(limit: int = 12,
                      user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """最近活动（TASK-040）— 来自真实 AgentExecution 表。"""
    q = (db.query(AgentExecution, Agent.name.label("agent_name"))
         .join(Agent, AgentExecution.agent_id == Agent.id, isouter=True))
    if user.company_id:
        q = q.filter(AgentExecution.company_id == user.company_id)
    rows = q.order_by(AgentExecution.id.desc()).limit(limit).all()

    items = [{
        "id": e.id,
        "actor": (agent_name or "系统"),
        "text": e.label or e.action,
        "status": e.status,
        "timestamp": e.created_at.strftime("%H:%M") if e.created_at else "",
    } for e, agent_name in rows]
    return {"items": items}
