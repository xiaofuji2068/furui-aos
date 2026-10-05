"""本体图探索 + Schema 演进 API（图谱 20-04 / 20-02）。

    GET  /api/ontology/related?type=&id=&depth=1~4
        → {root, nodes, edges, depth}  沿本体 Link 双向遍历（步骤 1.3）

    POST /api/ontology/revisions
        body: {"note": "新增 WorkOrder.status 字段"}
        → {version: "r2", note, commit_ts, id}

    GET  /api/ontology/revisions
        → [{version, note, commit_ts}, ...]  按 commit_ts 倒序

    GET  /api/ontology/snapshot
        → {nodes, edges, node_count, link_count, revision, pending, projected_at}
        图快照（Outbox+Projector，图谱 20-04）；读取时自动投影 pending 变更

    POST /api/ontology/snapshot/project
        → {projected, node_count, link_count, revision}  手动触发投影
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import require_perm
from ..db import get_db
from ..models import User
from ..models_ai import write_audit
from ..models_ontology import OntologySchemaRevision, bump_revision
from ..ontology import get_graph_snapshot, get_related, project_outbox

router = APIRouter(prefix="/ontology", tags=["本体图探索"])


@router.get("/related")
def related(
    type_name: str = Query(..., alias="type", description="对象类型，如 WorkOrder"),
    object_id: str = Query(..., alias="id", description="对象 id，如 WO-001"),
    depth: int = Query(1, ge=1, le=4, description="遍历深度 1~4"),
    user=Depends(require_perm("datasource:view")),
):
    """沿本体 Link 双向遍历，返回子图（节点 + 边）。"""
    r = get_related(type_name, object_id, depth)
    if not r["nodes"]:
        raise HTTPException(status_code=404, detail=f"对象 {type_name}/{object_id} 不存在")
    return r


# ---------------- Schema Revision（图谱 20-02）----------------


class RevisionOut(BaseModel):
    id: int
    version: str = Field(..., description="如 r1 / r2")
    note: str = ""
    commit_ts: Optional[str] = None

    class Config:
        from_attributes = True


class RevisionCreate(BaseModel):
    note: str = Field("", max_length=255, description="本次演进说明（写入审计）")


@router.get("/revisions", response_model=List[RevisionOut])
def list_revisions(
    user: User = Depends(require_perm("datasource:view")),
    db: Session = Depends(get_db),
):
    """列出所有 Schema 版本，按 commit_ts 倒序（图谱 20-02 演进历史）。"""
    rows = (
        db.query(OntologySchemaRevision)
        .filter(OntologySchemaRevision.company_id == (user.company_id or 1))
        .order_by(OntologySchemaRevision.created_at.desc())
        .all()
    )
    return [
        RevisionOut(
            id=r.id,
            version=r.revision,
            note=r.note or "",
            commit_ts=r.created_at.isoformat() if r.created_at else None,
        )
        for r in rows
    ]


@router.post("/revisions", response_model=RevisionOut)
def create_revision(
    body: RevisionCreate,
    user: User = Depends(require_perm("knowledge:manage")),
    db: Session = Depends(get_db),
):
    """打一个递增的新 Schema Revision（图谱 20-02 / 3.X.2 #1）。

    权限：knowledge:manage（与 publish_document 同级，schema 演进是治理动作）。
    行为：调用 bump_revision(db, note) → 自动 commit → 写审计 → 返回新版本。
    """
    note = (body.note or "").strip() or f"manual bump by {user.name}"

    # bump_revision 内部已 commit；此处不需要再 db.commit()
    new_version = bump_revision(db, note, company_id=user.company_id or 1)

    # 重新查一遍拿到 id / created_at（bump_revision 没返回 ORM 对象）
    row = (
        db.query(OntologySchemaRevision)
        .filter(OntologySchemaRevision.revision == new_version)
        .order_by(OntologySchemaRevision.id.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=500, detail="bump_revision 写后未查到记录")

    write_audit(
        db,
        action="ontology.bump_revision",
        actor_type="user",
        actor_id=user.id,
        actor_name=user.name,
        company_id=row.company_id,
        target=new_version,
        detail={"note": note, "revision_id": row.id},
        result="success",
    )
    db.commit()

    return RevisionOut(
        id=row.id,
        version=row.revision,
        note=row.note or "",
        commit_ts=row.created_at.isoformat() if row.created_at else None,
    )


# ---------------- Graph Snapshot（图谱 20-04 Outbox + Projector）----------------


@router.get("/snapshot")
def graph_snapshot(
    user: User = Depends(require_perm("datasource:view")),
    db: Session = Depends(get_db),
):
    """读取本体图快照；存在未投影的 Outbox 变更时先自动投影。

    验收口径（差距清单 #2）：写 N 条 Link 后，5s 内调用本接口即见全量图。
    """
    return get_graph_snapshot(db, company_id=user.company_id or 1)


@router.post("/snapshot/project")
def trigger_project(
    user: User = Depends(require_perm("knowledge:manage")),
    db: Session = Depends(get_db),
):
    """手动触发 Projector：消费全部 pending Outbox 并重建图快照。"""
    r = project_outbox(db, company_id=user.company_id or 1)
    write_audit(
        db,
        action="ontology.project_outbox",
        actor_type="user",
        actor_id=user.id,
        actor_name=user.name,
        company_id=user.company_id or 1,
        target="graph-full",
        detail={"projected": r.get("projected", 0),
                "node_count": r.get("node_count", 0),
                "link_count": r.get("link_count", 0)},
        result="success",
    )
    db.commit()
    return r
