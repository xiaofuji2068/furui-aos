"""审批中心 API（TASK-022）。

    GET  /api/approvals              待审批列表（可按状态过滤）
    GET  /api/approvals/{id}         详情：AI 理由 / 数据依据 / 执行计划 / 参数
    POST /api/approvals/{id}/approve 批准（可先修改参数再执行）
    POST /api/approvals/{id}/reject  拒绝

清单要求审批页必须能「查看 AI 原因、数据依据、执行计划」——
所以详情接口把 Approval 上的三类证据字段完整返回，前端不再二次拼装。
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import require_perm
from ..db import get_db
from ..models import User
from ..models_ai import ActionReceipt, Agent, Approval, ApprovalRule, SalesTask, write_audit
from ..tool_gateway import decide_approval

router = APIRouter(prefix="/approvals", tags=["审批中心"])

# 独立 router：若挂在 /approvals 下，/sales-tasks 会被 /{approval_id} 抢先匹配
router_sales = APIRouter(prefix="/sales-tasks", tags=["销售跟进任务"])


class DecideReq(BaseModel):
    comment: str = ""
    modified_payload: Optional[Dict[str, Any]] = None


def _brief(a: Approval, db: Session) -> Dict[str, Any]:
    agent = db.get(Agent, a.agent_id) if a.agent_id else None
    return {
        "id": a.id,
        "title": a.title,
        "action": a.action,
        "level": a.level,
        "status": a.status,
        "ai_reason": a.ai_reason,
        "agent": agent.name if agent else "",
        "agent_avatar": agent.avatar if agent else "",
        "task_id": a.task_id,
        "decided_by": a.decided_by,
        "decided_at": a.decided_at.isoformat() if a.decided_at else "",
        "comment": a.comment,
        "created_at": a.created_at.isoformat() if a.created_at else "",
    }


@router.get("")
def list_approvals(status: str = "Pending", limit: int = 50,
                   user: User = Depends(require_perm("approval:view")),
                   db: Session = Depends(get_db)):
    q = db.query(Approval)
    if user.company_id:
        q = q.filter(Approval.company_id == user.company_id)
    if status and status != "all":
        q = q.filter(Approval.status == status)
    rows = q.order_by(Approval.id.desc()).limit(limit).all()
    return {"total": len(rows), "items": [_brief(a, db) for a in rows]}


@router.get("/rules")
def list_rules(user: User = Depends(require_perm("approval:view")),
               db: Session = Depends(get_db)):
    """动作分级规则一览（TASK-021 四级分类）。"""
    q = db.query(ApprovalRule)
    if user.company_id:
        q = q.filter(ApprovalRule.company_id == user.company_id)
    rows = q.order_by(ApprovalRule.level.desc()).all()

    LEVEL_TEXT = {1: "自动执行", 2: "通知后执行", 3: "必须审批", 4: "禁止执行"}
    return {"items": [{
        "id": r.id, "action": r.action, "level": r.level,
        "level_text": LEVEL_TEXT.get(r.level, ""),
        "description": r.description, "approver_role": r.approver_role,
        "enabled": r.enabled,
    } for r in rows]}


@router.get("/{approval_id}")
def get_approval(approval_id: int,
                 user: User = Depends(require_perm("approval:view")),
                 db: Session = Depends(get_db)):
    a = db.get(Approval, approval_id)
    if not a:
        raise HTTPException(status_code=404, detail="审批单不存在")
    if user.company_id and a.company_id != user.company_id:
        raise HTTPException(status_code=403, detail="无权访问该审批单")

    def load(s: str) -> Any:
        try:
            return json.loads(s or "{}")
        except Exception:                                        # noqa: BLE001
            return {}

    # 动作凭证（图谱 Receipt）：该审批关联的全部执行留痕（含哈希，可复算核验）
    receipts = (db.query(ActionReceipt)
                .filter(ActionReceipt.approval_id == approval_id)
                .order_by(ActionReceipt.id.asc()).all())

    return {**_brief(a, db),
            "data_evidence": load(a.data_evidence),
            "plan": load(a.plan),
            "payload": load(a.payload),
            "decision_lineage": load(a.decision_lineage),
            "receipts": [{
                "id": r.id,
                "tool_name": r.tool_name,
                "params_hash": r.params_hash[:16] + "…",
                "result_hash": r.result_hash[:16] + "…",
                "actor_type": r.actor_type,
                "actor_id": r.actor_id,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            } for r in receipts]}


@router.post("/{approval_id}/approve")
def approve(approval_id: int, req: DecideReq,
            user: User = Depends(require_perm("approval:approve")),
            db: Session = Depends(get_db)):
    r = decide_approval(db, approval_id, user=user, decision="approve",
                        comment=req.comment, modified_payload=req.modified_payload)
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("error", "审批失败"))

    # 回带执行产物，便于前端展示「批准后立即生效」
    extra: Dict[str, Any] = {}
    if r.get("status") == "Executed":
        st = db.query(SalesTask).filter(SalesTask.approval_id == approval_id).first()
        if st:
            extra["sales_task"] = {
                "id": st.id, "title": st.title, "customer_name": st.customer_name,
                "owner": st.owner, "due_date": st.due_date, "status": st.status,
            }
    return {"ok": True, "approval_id": approval_id, "status": r.get("status"),
            "result": r.get("result"), **extra}


@router.post("/{approval_id}/reject")
def reject(approval_id: int, req: DecideReq,
           user: User = Depends(require_perm("approval:approve")),
           db: Session = Depends(get_db)):
    r = decide_approval(db, approval_id, user=user, decision="reject", comment=req.comment)
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("error", "操作失败"))
    return {"ok": True, "approval_id": approval_id, "status": "Rejected"}


@router_sales.get("")
def list_sales_tasks(limit: int = 50,
                     user: User = Depends(require_perm("approval:view")),
                     db: Session = Depends(get_db)):
    """Agent 已创建并生效的销售跟进任务，用于展示审批产出。"""
    q = db.query(SalesTask)
    if user.company_id:
        q = q.filter(SalesTask.company_id == user.company_id)
    rows = q.order_by(SalesTask.id.desc()).limit(limit).all()
    return {"items": [{
        "id": t.id, "title": t.title, "customer_name": t.customer_name,
        "priority": t.priority, "owner": t.owner, "due_date": t.due_date,
        "status": t.status, "source": t.source,
        "created_at": t.created_at.isoformat() if t.created_at else "",
    } for t in rows]}
