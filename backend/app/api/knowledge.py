"""企业知识中心 API（TASK-012 ~ TASK-015）。

    GET  /api/knowledge               知识资产总览（KPI / 健康度 / 提醒 / 分类）— 全部真实统计
    GET  /api/knowledge/bases         知识库列表
    POST /api/knowledge/bases         创建知识库
    GET  /api/knowledge/documents     文档列表（可按知识库过滤）
    POST /api/knowledge/documents     上传文档：解析 → 分块 → Embedding → 入库
    POST /api/knowledge/search        检索（语义+关键词混合、权限过滤、记录来源）

说明：健康度不写死，由四类真实信号加权算出；提醒项也由数据扫描生成。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_perm
from ..db import get_db
from ..models import User
from ..models_ai import (
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeDocument,
    write_audit,
)
from ..rag import index_document, search as rag_search

router = APIRouter(prefix="/knowledge", tags=["企业知识"])

# 知识分类的图标与配色（前端展示用，数据本身来自 kb.category 聚合）
CATEGORY_STYLE = {
    "企业制度": ("📋", "from-violet-500/40 to-purple-500/30"),
    "技术文档": ("🛠", "from-blue-500/40 to-cyan-500/30"),
    "产品资料": ("📦", "from-emerald-500/40 to-teal-500/30"),
    "设备资料": ("⚙️", "from-amber-500/40 to-orange-500/30"),
    "项目案例": ("🏗", "from-rose-500/40 to-pink-500/30"),
    "业务知识": ("📊", "from-violet-500/40 to-indigo-500/30"),
    "客户知识": ("👥", "from-cyan-500/40 to-blue-500/30"),
}


# ---------------- 统计口径 ----------------

def _visible_kb_ids(db: Session, user: User) -> List[int]:
    """按企业 + 部门可见范围过滤知识库 ID。"""
    q = db.query(KnowledgeBase)
    if user.company_id:
        q = q.filter(KnowledgeBase.company_id == user.company_id)
    rows = q.all()
    out = []
    dept = user.department_id
    for kb in rows:
        try:
            allowed = json.loads(kb.allowed_department_ids or "[]")
        except Exception:                                    # noqa: BLE001
            allowed = []
        if not allowed or (dept and dept in allowed):
            out.append(kb.id)
    return out


def _health(db: Session, kb_ids: List[int], docs: List[KnowledgeDocument]) -> Dict[str, Any]:
    """知识健康度：四个维度全部由真实数据算出，不做任何硬编码。"""
    total = len(docs)
    if total == 0:
        return {
            "score": 0, "level": "无数据", "delta": 0,
            "dimensions": [{"label": k, "value": 0}
                           for k in ("完整性", "准确性", "时效性", "一致性")],
            "basis": {},
        }

    now = datetime.utcnow()

    # 完整性：有正文且分片数 ≥ 1 的文档占比
    complete = sum(1 for d in docs if (d.char_count or 0) > 0 and (d.chunk_count or 0) > 0)

    # 准确性：记录了来源的文档占比（无来源的知识无法追溯，视为不可信）
    sourced = sum(1 for d in docs if (d.source or "").strip())

    # 时效性：未过期（无有效期或 valid_to 在未来）的文档占比
    fresh = 0
    for d in docs:
        if d.valid_to is None or d.valid_to >= now:
            fresh += 1

    # 一致性：状态为「已发布」的文档占比（草稿/审核中意味着尚未对齐）
    published = sum(1 for d in docs if d.status == "已发布")

    def pct(n: int) -> int:
        return int(round(n / total * 100))

    dims = [
        {"label": "完整性", "value": pct(complete)},
        {"label": "准确性", "value": pct(sourced)},
        {"label": "时效性", "value": pct(fresh)},
        {"label": "一致性", "value": pct(published)},
    ]
    # 准确性权重最高：来源可追溯是企业知识的底线
    score = int(round(sum(d["value"] * w for d, w in zip(dims, (0.25, 0.3, 0.2, 0.25)))))
    level = "优秀" if score >= 85 else "良好" if score >= 70 else "待改善" if score >= 50 else "较差"

    # 环比：与 30 天前相比新增了多少文档（近似上月增量）
    since = now - timedelta(days=30)
    recent = sum(1 for d in docs if (d.created_at or now) >= since)
    delta = int(round(recent / total * 100)) if total else 0

    return {
        "score": score, "level": level, "delta": delta,
        "dimensions": dims,
        "basis": {
            "docs": total, "complete": complete, "sourced": sourced,
            "fresh": fresh, "published": published, "recent_30d": recent,
        },
    }


def _reminders(docs: List[KnowledgeDocument]) -> List[Dict[str, Any]]:
    """知识治理提醒：由真实数据扫描生成，而非编造文案。"""
    now = datetime.utcnow()
    out: List[Dict[str, Any]] = []

    expired = [d for d in docs if d.valid_to and d.valid_to < now]
    if expired:
        out.append({
            "id": 1, "tag": "时效", "tagCls": "bg-rose-500/15 text-rose-300",
            "text": f"{len(expired)} 份文档已过有效期，建议复核更新",
        })

    expiring = [d for d in docs
                if d.valid_to and now <= d.valid_to <= now + timedelta(days=30)]
    if expiring:
        out.append({
            "id": 2, "tag": "预警", "tagCls": "bg-amber-500/15 text-amber-300",
            "text": f"{len(expiring)} 份文档将在 30 天内到期",
        })

    draft = [d for d in docs if d.status in ("草稿", "审核中")]
    if draft:
        out.append({
            "id": 3, "tag": "规范", "tagCls": "bg-violet-500/15 text-violet-300",
            "text": f"{len(draft)} 份文档尚未发布，Agent 不会引用",
        })

    nosrc = [d for d in docs if not (d.source or "").strip()]
    if nosrc:
        out.append({
            "id": 4, "tag": "溯源", "tagCls": "bg-cyan-500/15 text-cyan-300",
            "text": f"{len(nosrc)} 份文档缺少来源记录，引用时无法追溯",
        })

    return out


# ---------------- 总览 ----------------

@router.get("")
def overview(user: User = Depends(require_perm("knowledge:view")),
             db: Session = Depends(get_db)):
    kb_ids = _visible_kb_ids(db, user)
    kbs = db.query(KnowledgeBase).filter(KnowledgeBase.id.in_(kb_ids)).all() if kb_ids else []
    docs = (db.query(KnowledgeDocument)
            .filter(KnowledgeDocument.kb_id.in_(kb_ids)).all()) if kb_ids else []

    chunk_total = sum(d.chunk_count or 0 for d in docs)
    char_total = sum(d.char_count or 0 for d in docs)

    # 分类聚合：按知识库 category 统计文档数
    cat_map: Dict[str, int] = {}
    for kb in kbs:
        n = sum(1 for d in docs if d.kb_id == kb.id)
        cat_map[kb.category] = cat_map.get(kb.category, 0) + n
    categories = [{
        "name": name,
        "value": count,
        "icon": CATEGORY_STYLE.get(name, ("📁", "from-slate-500/40 to-slate-600/30"))[0],
        "color": CATEGORY_STYLE.get(name, ("📁", "from-slate-500/40 to-slate-600/30"))[1],
    } for name, count in sorted(cat_map.items(), key=lambda x: -x[1])]

    return {
        "title": "企业知识资产中心",
        "subtitle": "管理企业知识资产，提升 AI 智能化能力",
        "kpis": [
            {"label": "知识库",   "value": str(len(kbs)),  "unit": "个"},
            {"label": "知识文档", "value": str(len(docs)), "unit": "份"},
            {"label": "知识分片", "value": str(chunk_total), "unit": "条"},
            {"label": "累计字数", "value": f"{char_total:,}", "unit": "字"},
            {"label": "检索服务", "value": "已就绪", "unit": ""},
        ],
        "health": _health(db, kb_ids, docs),
        "reminders": _reminders(docs),
        "categories": categories,
    }


# ---------------- 知识库 CRUD ----------------

class KBCreate(BaseModel):
    name: str
    category: str = "业务知识"
    description: str = ""
    authority_level: int = 3
    allowed_department_ids: List[int] = []


@router.get("/bases")
def list_bases(user: User = Depends(require_perm("knowledge:view")),
               db: Session = Depends(get_db)):
    kb_ids = _visible_kb_ids(db, user)
    if not kb_ids:
        return {"items": []}
    rows = db.query(KnowledgeBase).filter(KnowledgeBase.id.in_(kb_ids)).all()
    return {"items": [{
        "id": kb.id, "name": kb.name, "category": kb.category,
        "description": kb.description,
        "authority_level": kb.authority_level, "status": kb.status,
        "doc_count": len(kb.documents),
        "chunk_count": sum(d.chunk_count or 0 for d in kb.documents),
        "created_at": kb.created_at.isoformat() if kb.created_at else "",
    } for kb in rows]}


@router.post("/bases")
def create_base(req: KBCreate,
                user: User = Depends(require_perm("knowledge:manage")),
                db: Session = Depends(get_db)):
    if not user.company_id:
        raise HTTPException(status_code=400, detail="账号未归属企业，无法创建知识库")
    kb = KnowledgeBase(
        company_id=user.company_id, name=req.name, category=req.category,
        description=req.description, authority_level=req.authority_level,
        allowed_department_ids=json.dumps(req.allowed_department_ids),
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    write_audit(db, action="knowledge.create_kb", actor_type="user",
                actor_id=user.id, actor_name=user.name, company_id=user.company_id,
                target=req.name, result="success")
    db.commit()
    return {"id": kb.id, "name": kb.name}


# ---------------- 文档 ----------------

@router.get("/documents")
def list_documents(kb_id: Optional[int] = None, limit: int = 100,
                   user: User = Depends(require_perm("knowledge:view")),
                   db: Session = Depends(get_db)):
    kb_ids = _visible_kb_ids(db, user)
    if not kb_ids:
        return {"items": []}
    q = db.query(KnowledgeDocument).filter(KnowledgeDocument.kb_id.in_(kb_ids))
    if kb_id:
        if kb_id not in kb_ids:
            raise HTTPException(status_code=403, detail="无权访问该知识库")
        q = q.filter(KnowledgeDocument.kb_id == kb_id)
    rows = q.order_by(KnowledgeDocument.id.desc()).limit(limit).all()
    return {"items": [{
        "id": d.id, "kb_id": d.kb_id, "title": d.title,
        "kb_name": d.kb.name if d.kb else "",
        "file_type": d.file_type, "source": d.source, "version": d.version,
        "status": d.status, "author": d.author,
        "chunk_count": d.chunk_count, "char_count": d.char_count,
        "valid_from": d.valid_from.isoformat() if d.valid_from else "",
        "valid_to": d.valid_to.isoformat() if d.valid_to else "",
        "created_at": d.created_at.isoformat() if d.created_at else "",
        "updated_at": d.updated_at.isoformat() if d.updated_at else "",
    } for d in rows]}


class DocCreate(BaseModel):
    kb_id: int
    title: str
    content: str
    source: str = ""
    file_type: str = "txt"
    status: str = "草稿"                # 上传强制草稿；发布必须走 submit -> publish 门禁
    valid_days: Optional[int] = None          # 有效期天数，None 表示长期有效
    version: int = 1


@router.post("/documents")
def create_document(req: DocCreate,
                    user: User = Depends(require_perm("knowledge:manage")),
                    db: Session = Depends(get_db)):
    """上传文档：文本 → 清洗 → 分块 → Embedding → 入库 → 可被 Agent 检索。"""
    kb = db.get(KnowledgeBase, req.kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if user.company_id and kb.company_id != user.company_id:
        raise HTTPException(status_code=403, detail="无权向该知识库写入")

    text = _clean(req.content)
    if not text.strip():
        raise HTTPException(status_code=400, detail="文档内容为空")
    if req.status not in ("草稿", "审核中"):
        raise HTTPException(status_code=400,
                            detail="上传状态仅允许草稿/审核中；发布必须走 submit -> publish 门禁")

    doc = KnowledgeDocument(
        kb_id=kb.id, company_id=kb.company_id, title=req.title,
        file_type=req.file_type, source=req.source, version=req.version,
        status=req.status,
        valid_from=datetime.utcnow(),
        valid_to=(datetime.utcnow() + timedelta(days=req.valid_days)) if req.valid_days else None,
        author=user.name, char_count=len(text),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 分块 + 向量化入库
    n = index_document(db, doc, text)
    doc.chunk_count = n
    db.commit()

    write_audit(db, action="knowledge.upload", actor_type="user",
                actor_id=user.id, actor_name=user.name, company_id=kb.company_id,
                target=req.title, detail={"kb_id": kb.id, "chunks": n, "chars": len(text)},
                result="success")
    db.commit()

    return {"id": doc.id, "title": doc.title, "chunk_count": n, "char_count": len(text)}


def _clean(text: str) -> str:
    """内容清洗：规整空白与不可见字符。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------- 检索 ----------------

class SearchReq(BaseModel):
    query: str
    top_k: int = 5
    kb_id: Optional[int] = None


@router.post("/search")
def do_search(req: SearchReq,
              user: User = Depends(require_perm("knowledge:view")),
              db: Session = Depends(get_db)):
    kb_ids = _visible_kb_ids(db, user)
    if req.kb_id:
        if req.kb_id not in kb_ids:
            raise HTTPException(status_code=403, detail="无权检索该知识库")
        kb_ids = [req.kb_id]

    r = rag_search(db, req.query, company_id=user.company_id, kb_ids=kb_ids,
                   department_id=user.department_id, top_k=req.top_k)
    return r


@router.post("/documents/{doc_id}/submit")
def submit_document(doc_id: int,
                    user: User = Depends(require_perm("knowledge:write")),
                    db: Session = Depends(get_db)):
    """草稿 -> 审核中（知识治理门禁，图谱 30-06）。"""
    doc = db.get(KnowledgeDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    if user.company_id and doc.company_id != user.company_id:
        raise HTTPException(status_code=403, detail="无权操作该文档")
    if doc.status != "草稿":
        raise HTTPException(status_code=400,
                            detail=f"仅草稿可提交审核，当前状态：{doc.status}")
    doc.status = "审核中"
    write_audit(db, action="knowledge.submit", actor_type="user", actor_id=user.id,
                actor_name=user.name, company_id=doc.company_id,
                target=doc.title, result="success")
    db.commit()
    return {"id": doc.id, "status": doc.status}


@router.post("/documents/{doc_id}/publish")
def publish_document(doc_id: int,
                     user: User = Depends(require_perm("knowledge:manage")),
                     db: Session = Depends(get_db)):
    """审核中 -> 已发布（发布后立即可被 Agent 检索，图谱 30-06）。"""
    doc = db.get(KnowledgeDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    if user.company_id and doc.company_id != user.company_id:
        raise HTTPException(status_code=403, detail="无权操作该文档")
    if doc.status != "审核中":
        raise HTTPException(status_code=400,
                            detail=f"仅审核中可发布，当前状态：{doc.status}")
    doc.status = "已发布"
    write_audit(db, action="knowledge.publish", actor_type="user", actor_id=user.id,
                actor_name=user.name, company_id=doc.company_id,
                target=doc.title, result="success")
    db.commit()
    return {"id": doc.id, "status": doc.status}


@router.get("/chunks")
def list_chunks(doc_id: int, limit: int = 50,
                user: User = Depends(require_perm("knowledge:view")),
                db: Session = Depends(get_db)):
    """查看某文档的分片，用于验证分块与入库效果。"""
    doc = db.get(KnowledgeDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    if user.company_id and doc.company_id != user.company_id:
        raise HTTPException(status_code=403, detail="无权访问该文档")

    rows = (db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.doc_id == doc_id)
            .order_by(KnowledgeChunk.id).limit(limit).all())
    return {"doc": {"id": doc.id, "title": doc.title, "status": doc.status},
            "items": [{"id": c.id, "seq": c.seq, "content": c.content} for c in rows]}
