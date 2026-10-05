"""低代码页面 API（40-03）：列表/详情/创建/更新/发布/删除 + 运行时取定义。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import get_current_user, require_perm
from ..db import SessionLocal
from ..models import User
from ..pages import (
    WIDGET_TYPES, list_pages, get_page, get_page_by_code,
    create_page, update_page, publish_page, delete_page,
)

router = APIRouter(prefix="/pages", tags=["lowcode"])


@router.get("/widget-types")
def widget_types(user: User = Depends(require_perm("tool:config"))):
    return {"items": [{"type": k, **v} for k, v in WIDGET_TYPES.items()]}


@router.get("")
def pages_list(user: User = Depends(require_perm("tool:config"))):
    db = SessionLocal()
    try:
        return {"items": list_pages(db, user.company_id)}
    finally:
        db.close()


class PageCreateReq(BaseModel):
    code: str
    title: str
    description: str = ""
    layout: List[Dict[str, Any]] = []


@router.post("")
def pages_create(req: PageCreateReq, user: User = Depends(require_perm("tool:config"))):
    db = SessionLocal()
    try:
        try:
            return create_page(db, user.company_id, req.code.strip(), req.title.strip(),
                               req.description, req.layout)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
    finally:
        db.close()


class PagePatchReq(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    layout: Optional[List[Dict[str, Any]]] = None


@router.put("/{page_id}")
def pages_update(page_id: int, req: PagePatchReq,
                 user: User = Depends(require_perm("tool:config"))):
    db = SessionLocal()
    try:
        p = update_page(db, user.company_id, page_id, req.dict(exclude_unset=True))
        if not p:
            raise HTTPException(status_code=404, detail="page not found")
        return p
    finally:
        db.close()


@router.post("/{page_id}/publish")
def pages_publish(page_id: int, user: User = Depends(require_perm("tool:config"))):
    db = SessionLocal()
    try:
        p = publish_page(db, user.company_id, page_id, "published")
        if not p:
            raise HTTPException(status_code=404, detail="page not found")
        return p
    finally:
        db.close()


@router.post("/{page_id}/draft")
def pages_to_draft(page_id: int, user: User = Depends(require_perm("tool:config"))):
    db = SessionLocal()
    try:
        p = publish_page(db, user.company_id, page_id, "draft")
        if not p:
            raise HTTPException(status_code=404, detail="page not found")
        return p
    finally:
        db.close()


@router.delete("/{page_id}")
def pages_delete(page_id: int, user: User = Depends(require_perm("tool:config"))):
    db = SessionLocal()
    try:
        if not delete_page(db, user.company_id, page_id):
            raise HTTPException(status_code=404, detail="page not found")
        return {"ok": True}
    finally:
        db.close()


@router.get("/by-code/{code}")
def page_by_code(code: str, user: User = Depends(get_current_user)):
    """运行时：登录用户读取页面定义（发布态优先；草稿仅供构建预览时带 token 访问）。"""
    db = SessionLocal()
    try:
        p = get_page_by_code(db, user.company_id, code)
        if not p:
            raise HTTPException(status_code=404, detail="page not found")
        return p
    finally:
        db.close()
