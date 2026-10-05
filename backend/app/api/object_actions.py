"""对象 AIP/Action 嵌入 API（图谱 40-04）。

GET  /api/objects/{type}/{id}              对象视图 + AIP/Action 表单（对象摘要 + 可执行动作）
POST /api/objects/{type}/{id}/actions/{action}  执行对象动作（写回门禁：权限/审批/Receipt）

权限：
- 查看对象/动作表单：datasource:view（与本体图探索一致）
- 执行动作：tool:use（动作本身还会在网关二次校验 required_permission，并按审批级别
  决定直行留 Receipt 或生成审批单）
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import require_perm
from ..db import get_db
from ..models import User
from ..object_actions import build_object_view, run_object_action

router = APIRouter(prefix="/objects")


class ActionReq(BaseModel):
    params: Dict[str, Any] = {}


@router.get("/{object_type}/{object_id}")
def object_view(
    object_type: str,
    object_id: str,
    user: User = Depends(require_perm("datasource:view")),
    db=Depends(get_db),
):
    """对象视图 + AIP/Action 表单（40-04 对象嵌入）。"""
    payload = build_object_view(db, user, object_type, object_id)
    if payload is None:
        raise HTTPException(status_code=404,
                            detail=f"对象 {object_type}/{object_id} 不存在")
    return payload


@router.post("/{object_type}/{object_id}/actions/{action}")
def run_action(
    object_type: str,
    object_id: str,
    action: str,
    req: ActionReq,
    user: User = Depends(require_perm("tool:use")),
    db=Depends(get_db),
):
    """执行对象动作：写回统一走 tool_gateway 门禁（权限/审批/Receipt/审计）。"""
    res = run_object_action(db, user, object_type, object_id, action, req.params)
    if res.get("ok"):
        return res
    if res.get("blocked"):
        # 待人工审批：返回审批单信息，前端引导去审批中心
        return res
    if res.get("reason") == "object_not_found":
        raise HTTPException(status_code=404, detail=res.get("error"))
    raise HTTPException(status_code=400, detail=res.get("error", "动作执行失败"))
