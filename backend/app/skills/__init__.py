"""Skills 工具箱 — Claude Skills / Computer Use 风格。

每个 AI 员工拥有专属 Skills，Skills 调到底层调用 Ontology Function / Object。
对 LLM 来说，Skills 就相当于 OpenAI 的 tool definitions。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

from ..ontology import ONTO, call_function, list_objects


@dataclass
class Skill:
    """一个 Skill = 一个可被 LLM 调用的工具。"""
    name: str
    description: str
    parameters: Dict[str, Any]                  # JSON Schema
    run: Callable[..., Dict[str, Any]]


# ---------- 通用工具 ----------

def _query_orders(region: str = None, status: str = None, limit: int = 50) -> Dict[str, Any]:
    orders = list_objects("Order", limit=limit)
    rows = []
    for o in orders:
        p = o.properties
        if region and p.get("region") != region:
            continue
        if status and p.get("status") != status:
            continue
        rows.append(p)
    return {"count": len(rows), "rows": rows}


def _query_products(low_stock_only: bool = False, threshold: int = 200) -> Dict[str, Any]:
    products = list_objects("Product")
    rows = []
    for p in products:
        props = p.properties
        if low_stock_only and props.get("stock", 0) >= threshold:
            continue
        rows.append(props)
    return {"count": len(rows), "rows": rows}


def _query_workorders(status: str = None) -> Dict[str, Any]:
    wos = list_objects("WorkOrder")
    rows = [w.properties for w in wos if (not status or w.properties.get("status") == status)]
    return {"count": len(rows), "rows": rows}


def _query_devices(status: str = None) -> Dict[str, Any]:
    devs = list_objects("Device")
    rows = [d.properties for d in devs if (not status or d.properties.get("status") == status)]
    return {"count": len(rows), "rows": rows}


def _query_kb(query: str) -> Dict[str, Any]:
    """知识库语义检索（演示：关键词匹配）。"""
    kb = {
        "设备维护手册": "定期巡检：3号监测站每周一次红外测温；备件更换周期 90 天。",
        "销售提成":   "A 类产品按 5% 提成；B 类按 3.5%；C 类按 4%；季度封顶 50,000。",
        "财务报表":   "现金流量表每周一上午 9:00 由 AI 员工自动生成；差异超过 5% 时标红告警。",
        "客户分级":   "A 类：年订单 ≥ 100 万；B 类：30 万 ≤ X < 100 万；C 类：< 30 万。",
        "应急流程":   "设备故障 → 自动建工单 → 通知现场工程师 → 严重时启动备机方案。",
    }
    hits = []
    for title, body in kb.items():
        if any(k in title + body for k in query.split()):
            hits.append({"title": title, "snippet": body[:120]})
    return {"count": len(hits), "rows": hits}


def _get_dashboard() -> Dict[str, Any]:
    """直接拉取首页 KPI + 洞察数据。"""
    orders = _query_orders()
    workorders = _query_workorders()
    devices = _query_devices()
    return {
        "kpis": {
            "orders": orders["count"],
            "workorders": workorders["count"],
            "devices": devices["count"],
        },
        "data": {
            "orders": orders["rows"],
            "workorders": workorders["rows"],
            "devices": devices["rows"],
        },
    }


# ---------- Skills 注册表 ----------

REGISTRY: Dict[str, Skill] = {}


def _reg(skill: Skill):
    REGISTRY[skill.name] = skill
    return skill


# 通用 Skills（任何 Agent 都能用）
_reg(Skill(
    name="query_orders",
    description="查询销售订单，可按区域/状态过滤",
    parameters={
        "type": "object",
        "properties": {
            "region": {"type": "string", "description": "区域过滤，如 '华东' / '华南' / '华西'，不传则全部"},
            "status": {"type": "string", "description": "状态过滤，如 '已下推' / '已完成'"},
            "limit":  {"type": "integer", "default": 50},
        },
    },
    run=_query_orders,
))

_reg(Skill(
    name="query_products",
    description="查询产品库存与价格",
    parameters={
        "type": "object",
        "properties": {
            "low_stock_only": {"type": "boolean", "description": "仅查询库存可能不足的产品"},
            "threshold":     {"type": "integer", "default": 200},
        },
    },
    run=_query_products,
))

_reg(Skill(
    name="query_workorders",
    description="查询设备工单",
    parameters={"type": "object", "properties": {"status": {"type": "string"}}},
    run=_query_workorders,
))

_reg(Skill(
    name="query_devices",
    description="查询设备在线状态",
    parameters={"type": "object", "properties": {"status": {"type": "string"}}},
    run=_query_devices,
))

_reg(Skill(
    name="query_kb",
    description="在企业知识库里检索答案（销售/财务/运维/制度等）",
    parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    run=_query_kb,
))

_reg(Skill(
    name="get_dashboard",
    description="拉取首页 KPI + AI 洞察卡片内容",
    parameters={"type": "object", "properties": {}},
    run=_get_dashboard,
))

# 写入型 Skills（高危 — 需人类确认）
_reg(Skill(
    name="create_workorder",
    description="创建一个设备维护工单（写入动作，需人类确认）",
    parameters={
        "type": "object",
        "properties": {
            "title":    {"type": "string"},
            "priority": {"type": "string", "enum": ["low", "medium", "high"]},
        },
        "required": ["title"],
    },
    run=lambda **kw: call_function("create_workorder", **kw),
))

_reg(Skill(
    name="send_notification",
    description="向企微/钉钉/邮箱发送一条通知（写入动作，需人类确认）",
    parameters={
        "type": "object",
        "properties": {
            "channel": {"type": "string"},
            "message": {"type": "string"},
        },
        "required": ["channel", "message"],
    },
    run=lambda **kw: call_function("send_notification", **kw),
))

_reg(Skill(
    name="draft_report",
    description="草拟一份主题报告（写入动作，需人类确认）",
    parameters={
        "type": "object",
        "properties": {
            "topic":    {"type": "string"},
            "audience": {"type": "string", "default": "管理层"},
        },
        "required": ["topic"],
    },
    run=lambda **kw: call_function("draft_report", **kw),
))


# ---------- 暴露给 LLM 的工具描述 ----------

def openai_tools(skill_names: List[str]) -> List[Dict[str, Any]]:
    """把指定 Skill 转成 OpenAI function-calling 工具格式。"""
    tools = []
    for n in skill_names:
        s = REGISTRY.get(n)
        if not s:
            continue
        tools.append({
            "type": "function",
            "function": {
                "name": s.name,
                "description": s.description,
                "parameters": s.parameters,
            },
        })
    return tools


def execute_skill(name: str, **kwargs) -> Dict[str, Any]:
    s = REGISTRY.get(name)
    if not s:
        return {"error": f"skill {name} not found"}
    try:
        return {"ok": True, "result": s.run(**kwargs)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# 写入型 Skills — 触发人类确认回路
WRITE_SKILLS = {"create_workorder", "send_notification", "draft_report"}
