"""Logic 决策编排画布 API（30-03）：图列表 / 详情 / 节点编辑 / 激活。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import require_perm
from ..db import SessionLocal
from ..models import User
from ..logic import list_graphs, get_graph, update_node, activate_graph

router = APIRouter(prefix="/logic", tags=["logic"])


@router.get("/graphs")
def graphs_list(user: User = Depends(require_perm("tool:config"))):
    db = SessionLocal()
    try:
        return {"items": list_graphs(db, user.company_id)}
    finally:
        db.close()


@router.get("/graphs/{graph_id}")
def graph_detail(graph_id: int, user: User = Depends(require_perm("tool:config"))):
    db = SessionLocal()
    try:
        g = get_graph(db, user.company_id, graph_id)
        if not g:
            raise HTTPException(status_code=404, detail="graph not found")
        return g
    finally:
        db.close()


class NodePatchReq(BaseModel):
    node_id: int
    title: Optional[str] = None
    kind: Optional[str] = None
    tool: Optional[str] = None
    label: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    depends: Optional[List[int]] = None


@router.post("/graphs/{graph_id}/nodes")
def patch_node(graph_id: int, req: NodePatchReq,
               user: User = Depends(require_perm("tool:config"))):
    db = SessionLocal()
    try:
        g = update_node(db, user.company_id, req.node_id, req.dict(exclude={"node_id"}))
        if not g:
            raise HTTPException(status_code=404, detail="node not found")
        return g
    finally:
        db.close()


@router.post("/graphs/{graph_id}/activate")
def activate(graph_id: int, user: User = Depends(require_perm("tool:config"))):
    db = SessionLocal()
    try:
        g = activate_graph(db, user.company_id, graph_id)
        if not g:
            raise HTTPException(status_code=404, detail="graph not found")
        return g
    finally:
        db.close()
