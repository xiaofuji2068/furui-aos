"""数据资产 API（图谱 10-01/10-02：Source→Sync→Dataset→Lineage/Health）。

GET    /api/data-assets            资产列表（含来源 / 血缘 / 健康）
GET    /api/data-assets/lineage    血缘链（source → datasets）
POST   /api/data-assets            新建资产（绑定数据源，source 不存在则 400）
DELETE /api/data-assets/{id}       删除资产
POST   /api/data-assets/{id}/sync  触发同步（模拟：行数 / 版本 / 健康 / 同步时间）

权限：查看 datasource:view，变更 datasource:config（与数据源管理一致）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import require_perm
from ..db import get_db
from ..models import User
from ..store_data_assets import (
    create_dataset,
    dataset_lineage,
    delete_dataset,
    list_datasets,
    sync_dataset,
)

router = APIRouter(prefix="/data-assets")


class AssetReq(BaseModel):
    name: str
    source_id: str
    kind: str = "table"
    entity: str = ""
    row_count: int = 0
    version: str = "v1"
    fields: List[str] = []
    lineage: Dict[str, Any] = {}


@router.get("")
def list_assets(_auth: User = Depends(require_perm("datasource:view")),
                db=Depends(get_db)):
    items = list_datasets(db, company_id=_auth.company_id or 1)
    return {"items": items, "total": len(items)}


@router.get("/lineage")
def lineage(_auth: User = Depends(require_perm("datasource:view")),
            db=Depends(get_db)):
    return dataset_lineage(db, company_id=_auth.company_id or 1)


@router.post("")
def create(req: AssetReq, _auth: User = Depends(require_perm("datasource:config")),
           db=Depends(get_db)):
    try:
        created = create_dataset(db, req.model_dump(), company_id=_auth.company_id or 1)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return created


@router.delete("/{asset_id}")
def remove(asset_id: int, _auth: User = Depends(require_perm("datasource:config")),
           db=Depends(get_db)):
    ok = delete_dataset(db, asset_id, company_id=_auth.company_id or 1)
    if not ok:
        raise HTTPException(status_code=404, detail=f"dataset asset '{asset_id}' not found")
    return {"ok": True, "id": asset_id}


@router.post("/{asset_id}/sync")
def sync(asset_id: int, _auth: User = Depends(require_perm("datasource:config")),
         db=Depends(get_db)):
    s = sync_dataset(db, asset_id, company_id=_auth.company_id or 1)
    if not s:
        raise HTTPException(status_code=404, detail=f"dataset asset '{asset_id}' not found")
    return s
