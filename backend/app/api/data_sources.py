"""数据源管理 API（60-03 治理：查看需 datasource:view，变更需 datasource:config）。

GET  /api/data-sources             列表
GET  /api/data-sources/catalog     可选目录
GET  /api/data-sources/{id}        详情
POST /api/data-sources             新增
DELETE /api/data-sources/{id}      删除
POST /api/data-sources/{id}/toggle 连接 / 断开切换
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import require_perm
from ..models import User
from ..store_data_sources import (
    list_sources, get_source, list_catalog,
    add_source, delete_source, toggle_source, overview_sources,
)

router = APIRouter(prefix="/data-sources")


class AddReq(BaseModel):
    id: Optional[str] = None
    name: str
    icon: str = "🔧"
    tone: str = "gray"
    category: str = "自定义"
    type: str = "api"
    desc: str = ""
    config: Dict[str, Any] = {}


@router.get("")
def list_all(_auth: User = Depends(require_perm("datasource:view"))):
    return {"items": list_sources(), "total": len(list_sources())}


@router.get("/catalog")
def catalog(_auth: User = Depends(require_perm("datasource:view"))):
    return {"items": list_catalog()}


@router.get("/overview")
def overview(_auth: User = Depends(require_perm("datasource:view"))):
    """给首页用的精简结构（含添加占位卡）。"""
    return {"items": overview_sources()}


@router.get("/{src_id}")
def detail(src_id: str, _auth: User = Depends(require_perm("datasource:view"))):
    s = get_source(src_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"data source '{src_id}' not found")
    return s


@router.post("")
def create(req: AddReq, _auth: User = Depends(require_perm("datasource:config"))):
    created = add_source(req.model_dump())
    if created is None:
        raise HTTPException(status_code=409, detail="id 重复或参数不合法")
    return created


@router.delete("/{src_id}")
def remove(src_id: str, _auth: User = Depends(require_perm("datasource:config"))):
    ok = delete_source(src_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"data source '{src_id}' not found")
    return {"ok": True, "id": src_id}


@router.post("/{src_id}/toggle")
def toggle(src_id: str, _auth: User = Depends(require_perm("datasource:config"))):
    s = toggle_source(src_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"data source '{src_id}' not found")
    return s
