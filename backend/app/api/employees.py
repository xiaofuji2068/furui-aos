"""AI 员工详细档案。

真实环境下这些字段的来源：
- `metrics`   → 从执行记录聚合（完成任务数 / 协助决策数 / 准确率）
- `logs`      → 从审计日志流读取
- `capabilities` → 绑定该员工的 Skills 注册表（见 app/skills/__init__.py）
- `permissions`  → 从 RBAC / Palantir 风权限矩阵读取
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models_ai import Agent, AgentSkill, Tool


# 标签配色放后端，前端直接渲染，避免前端再维护一份映射
TAG_CLS = {
    "完成":   "bg-emerald-500/15 text-emerald-300",
    "工单":   "bg-rose-500/15 text-rose-300",
    "未处理": "bg-amber-500/15 text-amber-300",
    "开始":   "bg-sky-500/15 text-sky-300",
    "分析":   "bg-violet-500/15 text-violet-300",
    "报告":   "bg-blue-500/15 text-blue-300",
}


EMPLOYEES: Dict[str, Dict[str, Any]] = {
    "设备运维工程师": {
        "name": "设备运维工程师",
        "role": "负责设备状态监测、故障排查、工单创建与派发",
        "avatar": "👷",
        "color": "from-sky-500 to-blue-500",
        "status": "working",
        "tags": [
            {"label": "智能化", "value": "0.6"},
            {"label": "自动化", "value": "0.8"},
        ],
        "metrics": [
            {"label": "完成任务", "value": 8,  "unit": "个"},
            {"label": "协助决策", "value": 6,  "unit": "项"},
            {"label": "准确率",   "value": 92, "unit": "%"},
        ],
        "logs": [
            {"time": "09:30", "event": "处理了 1 个异常事件",   "tag": "工单"},
            {"time": "09:15", "event": "检测设备运行状态良好", "tag": "完成"},
            {"time": "09:00", "event": "监测数据采集成功",     "tag": "完成"},
            {"time": "08:45", "event": "启动设备运行状态诊断", "tag": "完成"},
            {"time": "08:30", "event": "检测到异常状态",       "tag": "未处理"},
            {"time": "08:00", "event": "开始监测",             "tag": "开始"},
        ],
        "capabilities": [
            "设备故障诊断", "参数自动调整", "维护计划制定",
            "应急预案生成", "工单自动派发", "维修经验总结",
        ],
        "permissions": [
            {"name": "设备监控", "granted": True},
            {"name": "工单创建", "granted": True},
            {"name": "参数调整", "granted": True},
            {"name": "维修建议", "granted": True},
            {"name": "采购审批", "granted": False},
            {"name": "设备停机", "granted": False},
        ],
    },

    "销售分析师": {
        "name": "销售分析师",
        "role": "负责销售订单分析、异常识别与增长机会挖掘",
        "avatar": "👨‍💼",
        "color": "from-rose-500 to-orange-500",
        "status": "working",
        "tags": [
            {"label": "智能化", "value": "0.8"},
            {"label": "自动化", "value": "0.5"},
        ],
        "metrics": [
            {"label": "完成任务", "value": 12, "unit": "个"},
            {"label": "协助决策", "value": 9,  "unit": "项"},
            {"label": "准确率",   "value": 88, "unit": "%"},
        ],
        "logs": [
            {"time": "10:20", "event": "识别出华东区域订单下滑 18%", "tag": "分析"},
            {"time": "10:05", "event": "拉取本周订单明细",           "tag": "完成"},
            {"time": "09:50", "event": "对比去年同期数据",           "tag": "完成"},
            {"time": "09:30", "event": "生成销售数据快照",           "tag": "报告"},
            {"time": "09:00", "event": "启动每日销售巡检",           "tag": "开始"},
        ],
        "capabilities": [
            "销售趋势分析", "区域对比分析", "客户分层",
            "异常归因", "增长机会挖掘", "周报自动生成",
        ],
        "permissions": [
            {"name": "订单查询", "granted": True},
            {"name": "客户数据", "granted": True},
            {"name": "报表生成", "granted": True},
            {"name": "通知推送", "granted": True},
            {"name": "价格调整", "granted": False},
            {"name": "合同审批", "granted": False},
        ],
    },

    "财务助手": {
        "name": "财务助手",
        "role": "负责现金流分析、预算差异说明与财务报表生成",
        "avatar": "👩‍💼",
        "color": "from-emerald-500 to-teal-500",
        "status": "idle",
        "tags": [
            {"label": "智能化", "value": "0.7"},
            {"label": "自动化", "value": "0.6"},
        ],
        "metrics": [
            {"label": "完成任务", "value": 6,  "unit": "个"},
            {"label": "协助决策", "value": 4,  "unit": "项"},
            {"label": "准确率",   "value": 96, "unit": "%"},
        ],
        "logs": [
            {"time": "11:00", "event": "生成资金流动分析报告",   "tag": "报告"},
            {"time": "10:40", "event": "核算应收账款回款率 78%", "tag": "完成"},
            {"time": "10:15", "event": "启动现金流巡检",         "tag": "开始"},
        ],
        "capabilities": [
            "现金流分析", "损益回顾", "预算差异说明",
            "报表自动汇总", "回款提醒", "成本结构拆解",
        ],
        "permissions": [
            {"name": "财务数据", "granted": True},
            {"name": "报表生成", "granted": True},
            {"name": "回款提醒", "granted": True},
            {"name": "付款审批", "granted": False},
            {"name": "预算调整", "granted": False},
        ],
    },

    "知识助手": {
        "name": "知识助手",
        "role": "负责企业知识检索、归纳与知识库维护",
        "avatar": "🧑‍🏫",
        "color": "from-violet-500 to-purple-500",
        "status": "working",
        "tags": [
            {"label": "智能化", "value": "0.9"},
            {"label": "自动化", "value": "0.4"},
        ],
        "metrics": [
            {"label": "完成任务", "value": 15, "unit": "个"},
            {"label": "协助决策", "value": 11, "unit": "项"},
            {"label": "准确率",   "value": 90, "unit": "%"},
        ],
        "logs": [
            {"time": "11:30", "event": "更新《设备维护手册》",   "tag": "完成"},
            {"time": "11:10", "event": "整理运维 SOP 共 12 条", "tag": "完成"},
            {"time": "10:50", "event": "检索制度文档 8 份",     "tag": "分析"},
            {"time": "10:30", "event": "启动知识库巡检",         "tag": "开始"},
        ],
        "capabilities": [
            "知识语义检索", "文档归纳总结", "SOP 生成",
            "知识库去重", "引用溯源", "术语标准化",
        ],
        "permissions": [
            {"name": "知识读取", "granted": True},
            {"name": "知识写入", "granted": True},
            {"name": "文档归纳", "granted": True},
            {"name": "知识删除", "granted": False},
            {"name": "权限变更", "granted": False},
        ],
    },
}


def list_employee_names() -> List[str]:
    return list(EMPLOYEES.keys())


def _agent_code(name: str) -> str:
    ascii_name = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return (ascii_name or f"custom-agent-{abs(hash(name)) % 100000}")[:64]


def create_employee(data: Dict[str, Any], db: Session | None = None,
                    company_id: int | None = None) -> Dict[str, Any]:
    """创建向导调用：写入员工档案库，并同步到运行时注册表。"""
    name = (data.get("name") or "").strip()
    if not name:
        return {"error": "员工名称不能为空"}
    if name in EMPLOYEES:
        return {"error": f"员工「{name}」已存在"}

    if db is not None and company_id:
        existing = (db.query(Agent)
                    .filter(Agent.company_id == company_id, Agent.name == name)
                    .first())
        if existing:
            return {"error": f"员工「{name}」已存在"}

    role = (data.get("role") or "自定义 AI 员工").strip()
    avatar = data.get("avatar") or "🤖"
    color = data.get("color") or "from-violet-500 to-blue-500"
    skills = data.get("skills") or []
    capabilities = data.get("capabilities") or ["通用分析"]
    permissions = data.get("permissions") or [{"name": "基础查询", "granted": True}]

    EMPLOYEES[name] = {
        "name": name,
        "role": role,
        "avatar": avatar,
        "color": color,
        "status": "idle",
        "tags": [
            {"label": "智能化", "value": "0.5"},
            {"label": "自动化", "value": "0.5"},
        ],
        "metrics": [
            {"label": "完成任务", "value": 0, "unit": "个"},
            {"label": "协助决策", "value": 0, "unit": "项"},
            {"label": "准确率", "value": 95, "unit": "%"},
        ],
        "logs": [{"time": "现在", "event": f"创建 AI 员工「{name}」", "tag": "开始"}],
        "capabilities": capabilities,
        "permissions": permissions,
    }

    # 数据库 Agent 是执行链的真相来源；内存注册仅用于兼容旧版聊天路由。
    if db is not None and company_id:
        code = _agent_code(name)
        if db.query(Agent).filter(Agent.company_id == company_id, Agent.code == code).first():
            code = f"{code[:55]}-{abs(hash(name)) % 100000:05d}"
        tool_names = [s for s in skills if isinstance(s, str)] or ["get_dashboard"]
        tool_rows = db.query(Tool).filter(
            Tool.company_id == company_id, Tool.name.in_(tool_names)
        ).all()
        agent = Agent(
            company_id=company_id,
            name=name,
            code=code,
            description=role,
            avatar=avatar,
            position=role,
            agent_type="assistant",
            status="Published",
            system_prompt=f"你是「{name}」，负责{role}。",
            goal=role,
            rules="写入型操作必须经过人工审批。",
            allowed_tool_ids=json.dumps([t.id for t in tool_rows]),
            allowed_actions=json.dumps(["read", "analyze", "write"]),
            approval_level=3,
        )
        db.add(agent)
        db.flush()
        for tool in tool_rows:
            db.add(AgentSkill(agent_id=agent.id, skill_name=tool.name, enabled=True))
        db.commit()

    # 同步到 agents 运行时，让旧版 /api/chat-stream 也能看到
    from ..agents import employees as agents_mod
    agents_mod.register_agent(
        name=name, role=role, avatar=avatar, color=color, skills=skills,
    )
    return {"ok": True, "name": name}


def delete_employee(name: str, db: Session | None = None,
                    company_id: int | None = None) -> Dict[str, Any]:
    """删除员工（同时移出运行时注册表）。"""
    if name not in EMPLOYEES:
        return {"error": f"员工「{name}」不存在"}
    EMPLOYEES.pop(name)
    if db is not None and company_id:
        agent = (db.query(Agent)
                 .filter(Agent.company_id == company_id, Agent.name == name)
                 .first())
        if agent:
            db.delete(agent)
            db.commit()
    from ..agents import employees as agents_mod
    agents_mod.REGISTRY_AGENTS.pop(name, None)
    return {"ok": True, "name": name}


def get_employee_payload(name: str) -> Optional[Dict[str, Any]]:
    """返回单个员工的完整档案（含前端渲染所需的 tag 配色）。"""
    e = EMPLOYEES.get(name)
    if not e:
        return None
    # 给每条日志补上配色类名
    logs = []
    for l in e["logs"]:
        logs.append({**l, "tagCls": TAG_CLS.get(l["tag"], "bg-gray-500/15 text-gray-300")})
    return {**e, "logs": logs}
