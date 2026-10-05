"""主线执行 API（TASK-007 对话引擎 / TASK-008 过程可视化 / TASK-009 任务中心）。

    POST /api/mainline/run    SSE 流式执行主线任务，六步过程实时推送
    GET  /api/tasks           真实任务列表（替代旧的内存 _TASKS）
    GET  /api/tasks/{id}      任务详情：步骤 + 每一步的执行日志

SSE 会话生命周期说明：
    路由函数返回后，Depends(get_db) 注入的 session 会被关闭，
    而 SSE 生成器此时还在跑。所以这里手动开一个 Session，
    在生成器结束时关闭 —— 否则流到一半就断连。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_perm
from ..db import SessionLocal, get_db
from ..mainline import MainlineRunner
from ..models import User
from ..models_ai import (
    Agent, AgentExecution, AgentStage, AgentStep, AgentTask, TaskReview, write_audit,
)

router = APIRouter(prefix="/mainline", tags=["主线执行"])


class RunReq(BaseModel):
    question: str
    agent_code: str = "sales-analyst"
    conversation_id: str = ""


async def _stream(runner: MainlineRunner, question: str, db: Session) -> AsyncIterator[Dict[str, str]]:
    try:
        async for ev in runner.run(question):
            yield {
                "event": ev["event"],
                "data": json.dumps(ev["data"], ensure_ascii=False),
            }
    except Exception as e:                                       # noqa: BLE001
        yield {"event": "error", "data": json.dumps({"message": f"{type(e).__name__}: {e}"}, ensure_ascii=False)}
    finally:
        db.close()


@router.post("/run")
async def run_mainline(req: RunReq, user: User = Depends(require_perm("employee:execute"))):
    """执行主线任务，SSE 推送全过程。

    事件类型：
      task        任务已创建，含执行计划
      step        步骤状态变化（Running / Completed / Skipped）
      tool_result 工具调用结果（ERP / CRM / 知识 / 归因）
      token       报告正文流式输出
      pending     需要人工审批
      done        完成，含最终状态与进度
      error       执行异常
    """
    from sse_starlette.sse import EventSourceResponse

    db = SessionLocal()
    try:
        agent = (db.query(Agent)
                 .filter(Agent.company_id == user.company_id, Agent.code == req.agent_code)
                 .first())
        if not agent:
            db.close()
            raise HTTPException(status_code=404, detail=f"未找到 Agent：{req.agent_code}")
        if agent.status not in ("Published", "Running", "Testing"):
            db.close()
            raise HTTPException(status_code=400, detail=f"Agent 当前状态不可执行：{agent.status}")

        runner = MainlineRunner(db, agent, user,
                                company_id=user.company_id or 0,
                                conversation_id=req.conversation_id)
    except HTTPException:
        raise
    except Exception as e:                                       # noqa: BLE001
        db.close()
        raise HTTPException(status_code=500, detail=str(e))

    return EventSourceResponse(_stream(runner, req.question, db))


router_tasks = APIRouter(prefix="/tasks", tags=["任务中心"])


def _user_names(db: Session, ids: List[int]) -> Dict[int, str]:
    """批量解析用户名（AgentTask 只存 user_id，无关系属性）。"""
    ids = [i for i in ids if i]
    if not ids:
        return {}
    rows = db.query(User.id, User.name).filter(User.id.in_(ids)).all()
    return {r[0]: r[1] for r in rows}


def _task_brief(t: AgentTask, uname: str = "") -> Dict[str, Any]:
    return {
        "id": t.id,
        "title": t.title,
        "status": t.status,
        "mode": t.mode,
        "progress": t.progress,
        "priority": t.priority,
        "agent": t.agent.name if t.agent else "",
        "agent_avatar": t.agent.avatar if t.agent else "",
        "user": uname,
        "created_at": t.created_at.isoformat() if t.created_at else "",
        "finished_at": t.finished_at.isoformat() if t.finished_at else "",
        "step_count": len(t.steps),
        "steps_done": sum(1 for s in t.steps if s.status in ("Completed", "Skipped")),
        "error": t.error,
        "retry_count": t.retry_count,
    }


def _stages_of(t: AgentTask) -> List[Dict[str, Any]]:
    return [{
        "seq": st.seq,
        "name": st.name,
        "kind": st.kind,
        "status": st.status,
        "steps": [s for s in st.step_list],
        "checkpoint": json.loads(st.checkpoint or "{}"),
        "started_at": st.started_at.isoformat() if st.started_at else "",
        "finished_at": st.finished_at.isoformat() if st.finished_at else "",
    } for st in sorted(t.stages, key=lambda x: x.seq)]


def _reviews_of(db: Session, t: AgentTask) -> List[Dict[str, Any]]:
    rows = (db.query(TaskReview)
            .filter(TaskReview.task_id == t.id)
            .order_by(TaskReview.id).all())
    return [{
        "id": r.id,
        "stage": r.stage_id,
        "reviewer": r.reviewer_name,
        "decision": r.decision,
        "comment": r.comment,
        "created_at": r.created_at.isoformat() if r.created_at else "",
    } for r in rows]


@router_tasks.get("")
def task_list(status: Optional[str] = None, limit: int = 50,
              user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    q = db.query(AgentTask)
    if user.company_id:
        q = q.filter(AgentTask.company_id == user.company_id)
    if status:
        q = q.filter(AgentTask.status == status)
    rows = q.order_by(AgentTask.id.desc()).limit(limit).all()
    names = _user_names(db, [t.user_id for t in rows])
    return {"total": len(rows), "items": [_task_brief(t, names.get(t.user_id, "")) for t in rows]}


@router_tasks.get("/{task_id}")
def task_detail(task_id: int,
                user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    t = db.get(AgentTask, task_id)
    if not t:
        raise HTTPException(status_code=404, detail="任务不存在")
    if user.company_id and t.company_id != user.company_id:
        raise HTTPException(status_code=403, detail="无权访问该任务")

    execs = (db.query(AgentExecution)
             .filter(AgentExecution.task_id == t.id)
             .order_by(AgentExecution.id).all())

    try:
        brief = json.loads(t.brief or "{}")
    except (TypeError, ValueError):
        brief = {}

    return {
        **_task_brief(t, _user_names(db, [t.user_id]).get(t.user_id, "")),
        "input_text": t.input_text,
        "result": t.result,
        "conversation_id": t.conversation_id,
        "brief": brief,
        "stages": _stages_of(t),
        "reviews": _reviews_of(db, t),
        "steps": [{
            "seq": s.seq, "title": s.title, "kind": s.kind,
            "status": s.status, "depends_on": s.deps,
            "started_at": s.started_at.isoformat() if s.started_at else "",
            "finished_at": s.finished_at.isoformat() if s.finished_at else "",
            "error": s.error,
        } for s in sorted(t.steps, key=lambda x: x.seq)],
        "executions": [{
            "id": e.id, "action": e.action, "label": e.label, "status": e.status,
            "tool_name": e.tool_name, "duration_ms": e.duration_ms, "error": e.error,
            "created_at": e.created_at.isoformat() if e.created_at else "",
        } for e in execs],
    }


class ReviewReq(BaseModel):
    decision: str          # approve | return
    comment: str = ""


@router_tasks.post("/{task_id}/review")
def task_review(task_id: int, req: ReviewReq,
                user: User = Depends(require_perm("approval:approve")),
                db: Session = Depends(get_db)):
    """人工复核（TASK-012 Review/Return）：审批人复核任务产物后放行或退回。

    - approve：任务 → Completed（人工验收通过）
    - return：  任务 → Returned（产物不合格，退回可重跑）
    """
    t = db.get(AgentTask, task_id)
    if not t:
        raise HTTPException(status_code=404, detail="任务不存在")
    if user.company_id and t.company_id != user.company_id:
        raise HTTPException(status_code=403, detail="无权操作该任务")

    if req.decision not in ("approve", "return"):
        raise HTTPException(status_code=400, detail="decision 仅支持 approve / return")
    target = "Completed" if req.decision == "approve" else "Returned"
    if not t.transition(target):
        raise HTTPException(status_code=400,
                            detail=f"当前状态 {t.status} 不允许执行 {req.decision} 复核")

    db.add(TaskReview(
        company_id=t.company_id, task_id=t.id,
        stage_id=t.stages[-1].id if t.stages else None,
        reviewer_id=user.id, reviewer_name=user.name,
        decision=req.decision, comment=req.comment,
    ))
    if target == "Completed":
        t.finished_at = t.finished_at or datetime.utcnow()
    else:
        t.error = f"复核退回：{req.comment or '未填写意见'}"
    write_audit(db, action="task.review", actor_type="user", actor_id=user.id,
                actor_name=user.name, company_id=t.company_id, target=f"task#{t.id}",
                detail={"decision": req.decision, "comment": req.comment}, result="success")
    db.commit()
    return {"ok": True, "task_id": t.id, "status": t.status}


@router_tasks.post("/{task_id}/retry")
async def task_retry(task_id: int, req: RunReq,
                     user: User = Depends(require_perm("employee:execute"))):
    """重跑（TASK-012）：Returned / Failed 任务复用同一任务重跑，SSE 推送全过程。"""
    from sse_starlette.sse import EventSourceResponse

    db = SessionLocal()
    try:
        t = db.get(AgentTask, task_id)
        if not t:
            db.close()
            raise HTTPException(status_code=404, detail="任务不存在")
        if user.company_id and t.company_id != user.company_id:
            db.close()
            raise HTTPException(status_code=403, detail="无权操作该任务")
        if t.status not in ("Returned", "Failed"):
            db.close()
            raise HTTPException(status_code=400, detail=f"仅 Returned / Failed 任务可重跑，当前 {t.status}")
        agent = (db.query(Agent)
                 .filter(Agent.company_id == user.company_id, Agent.code == req.agent_code)
                 .first())
        if not agent:
            db.close()
            raise HTTPException(status_code=404, detail=f"未找到 Agent：{req.agent_code}")
        runner = MainlineRunner(db, agent, user,
                                company_id=user.company_id or 0,
                                conversation_id=req.conversation_id)
    except HTTPException:
        raise
    except Exception as e:                                       # noqa: BLE001
        db.close()
        raise HTTPException(status_code=500, detail=str(e))

    async def _retry_stream():
        try:
            async for ev in runner.run(t.input_text or req.question, existing=t):
                yield {
                    "event": ev["event"],
                    "data": json.dumps(ev["data"], ensure_ascii=False),
                }
        except Exception as e:                                   # noqa: BLE001
            yield {"event": "error",
                   "data": json.dumps({"message": f"{type(e).__name__}: {e}"}, ensure_ascii=False)}
        finally:
            db.close()

    return EventSourceResponse(_retry_stream())
