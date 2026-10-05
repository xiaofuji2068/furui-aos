"""对象 AIP/Action 嵌入（图谱 40-04）。

对象视图（本体图对象 Customer/Device/WorkOrder/...）上的动作表单 + 写回门禁：
- 动作目录 OBJECT_ACTIONS 定义"对象类型 → 可执行动作"，动作映射到 tool_gateway 已注册工具
- 动作执行统一走 tool_gateway.execute：四级门禁（Agent 白名单 / 用户权限 / 参数校验 / 审批）+ Receipt + 审计
- 写回不再绕过门禁：Level1/2 直行留 Receipt，Level3 生成审批单（人工批准后才执行）

说明：
- 目录只暴露 tool_gateway.IMPL 里有实现的工具（如 create_workorder 仅注册无实现，不暴露）
- "*" 表示所有对象类型通用的动作
- 对象上下文（object_type/object_id/object_name）在执行时自动注入参数，不覆盖用户显式传值
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .models_ai import Tool
from .ontology import list_objects
from .tool_gateway import ToolContext, execute as gateway_execute

# 对象类型 → 可用动作（action 必须对应 _ACTION_TOOL 中的网关工具名）
OBJECT_ACTIONS: Dict[str, List[Dict[str, Any]]] = {
    "*": [
        {"action": "send_notification", "label": "发送通知",
         "params": [
             {"name": "message", "label": "通知内容", "type": "string", "required": True},
             {"name": "channel", "label": "渠道（企微/邮件）", "type": "string", "required": False},
         ]},
        {"action": "draft_report", "label": "生成分析报告",
         "params": [
             {"name": "topic", "label": "报告主题", "type": "string", "required": True},
             {"name": "audience", "label": "受众（默认管理层）", "type": "string", "required": False},
         ]},
    ],
    "Customer": [
        {"action": "create_sales_task", "label": "创建跟进任务",
         "params": [
             {"name": "title", "label": "任务标题", "type": "string", "required": True},
             {"name": "detail", "label": "任务详情", "type": "string", "required": False},
             {"name": "priority", "label": "优先级（high/medium/low）", "type": "string", "required": False},
             {"name": "owner", "label": "负责人", "type": "string", "required": False},
             {"name": "due_date", "label": "截止日期", "type": "string", "required": False},
         ]},
    ],
}

# action 标识 → 网关工具名（工具必须存在于 tool_gateway.IMPL）
_ACTION_TOOL: Dict[str, str] = {
    "send_notification": "send_notification",
    "draft_report": "draft_report",
    "create_sales_task": "create_sales_task",
}


def get_object(object_type: str, object_id: str) -> Optional[Dict[str, Any]]:
    """按类型 + id 查本体图对象（DB 优先，空表回退内存）。"""
    for o in list_objects(object_type, limit=500):
        if o.id == object_id:
            props = o.properties or {}
            return {
                "id": o.id,
                "type": o.type,
                "name": props.get("name") or o.id,
                "properties": props,
            }
    return None


def build_object_view(db: Session, user, object_type: str,
                      object_id: str) -> Optional[Dict[str, Any]]:
    """对象视图 + AIP/Action 表单：对象摘要 + 用户可见动作（无权限动作过滤掉）。"""
    obj = get_object(object_type, object_id)
    if not obj:
        return None

    defs = list(OBJECT_ACTIONS.get("*", [])) + list(OBJECT_ACTIONS.get(object_type, []))
    actions: List[Dict[str, Any]] = []
    for d in defs:
        tool_name = _ACTION_TOOL.get(d["action"])
        if not tool_name:
            continue
        tool = (db.query(Tool)
                .filter(Tool.company_id == (user.company_id or 1),
                        Tool.name == tool_name,
                        Tool.status == "active")
                .first())
        if not tool:
            continue
        if tool.required_permission and not user.has_perm(tool.required_permission):
            continue  # 用户无权限的动作不出现在表单里（后端仍会在网关二次校验）
        actions.append({
            "action": d["action"],
            "label": d["label"],
            "params": d["params"],
            "level": tool.action_level,
            "required_permission": tool.required_permission,
            "tool": tool_name,
        })

    return {"object": obj, "actions": actions}


def run_object_action(db: Session, user, object_type: str, object_id: str,
                      action: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """执行对象动作（写回门禁）：统一走 tool_gateway.execute。

    返回与网关一致的三态：
      {"ok": True, "result": ..., "receipt_id": n, "level": ...}   已执行（写回留凭证）
      {"ok": False, "blocked": True, "approval_id": n, ...}        需人工审批（Level 3）
      {"ok": False, "error": "...", "reason": ...}                 被拒绝 / 失败
    """
    obj = get_object(object_type, object_id)
    if not obj:
        return {"ok": False, "error": f"对象 {object_type}/{object_id} 不存在",
                "reason": "object_not_found"}
    tool_name = _ACTION_TOOL.get(action)
    if not tool_name:
        return {"ok": False, "error": f"动作 {action} 不支持",
                "reason": "action_not_supported"}

    merged: Dict[str, Any] = dict(params or {})
    # 注入对象上下文（setdefault：不覆盖用户显式传参）
    merged.setdefault("object_type", object_type)
    merged.setdefault("object_id", object_id)
    merged.setdefault("object_name", obj["name"])

    ctx = ToolContext(db=db, user=user, company_id=user.company_id or 1)
    return gateway_execute(ctx, tool_name, merged)
