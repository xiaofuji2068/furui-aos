"""数据资产 store（图谱 10-01 Source→Sync→Dataset→Lineage/Health 资产链）。

Dataset 资产挂在数据源之上（store_data_sources 的内存源）：
- source_id 引用数据源 id（erp/crm/mes/...），不存在则拒绝创建
- 血缘以 JSON 存 dataset 的 upstream/downstream（最小可用版）
- 健康状态由 sync 动作维护；真实接入时替换为真实同步/健康探测，接口形态不变
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from .models_ai import DatasetAsset
from .store_data_sources import get_source


def _asset_dict(row: DatasetAsset) -> Dict[str, Any]:
    src = get_source(row.source_id) or {}
    return {
        "id": row.id,
        "source_id": row.source_id,
        "source_name": src.get("name", row.source_id),
        "source_status": src.get("status", ""),
        "name": row.name,
        "kind": row.kind,
        "entity": row.entity,
        "row_count": row.row_count,
        "version": row.version,
        "fields": row.schema_fields,
        "lineage": row.lineage,
        "health_status": row.health_status,
        "last_sync_at": row.last_sync_at.isoformat() if row.last_sync_at else None,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def list_datasets(db, company_id: int = 1) -> List[Dict[str, Any]]:
    rows = (db.query(DatasetAsset)
            .filter_by(company_id=company_id)
            .order_by(DatasetAsset.id)
            .all())
    return [_asset_dict(r) for r in rows]


def get_dataset(db, dataset_id: int, company_id: int = 1) -> Optional[Dict[str, Any]]:
    row = (db.query(DatasetAsset)
           .filter_by(id=dataset_id, company_id=company_id)
           .first())
    return _asset_dict(row) if row else None


def create_dataset(db, payload: Dict[str, Any], company_id: int = 1) -> Dict[str, Any]:
    """新建数据资产：校验数据源存在 + 名称必填，写入后立即置为已同步（healthy）。"""
    source_id = (payload.get("source_id") or "").strip()
    if not source_id or not get_source(source_id):
        raise ValueError(f"data source '{source_id}' not found")
    name = (payload.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    lineage = payload.get("lineage") or {"upstream": [], "downstream": []}
    if not isinstance(lineage, dict):
        lineage = {"upstream": [], "downstream": []}
    row = DatasetAsset(
        company_id=company_id,
        source_id=source_id,
        name=name,
        kind=payload.get("kind", "table") or "table",
        entity=payload.get("entity", "") or "",
        row_count=int(payload.get("row_count") or 0),
        version=payload.get("version") or "v1",
        schema_json=json.dumps(payload.get("fields", []), ensure_ascii=False),
        lineage_json=json.dumps(lineage, ensure_ascii=False),
        health_status="healthy",
        last_sync_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _asset_dict(row)


def delete_dataset(db, dataset_id: int, company_id: int = 1) -> bool:
    row = (db.query(DatasetAsset)
           .filter_by(id=dataset_id, company_id=company_id)
           .first())
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def sync_dataset(db, dataset_id: int, company_id: int = 1) -> Optional[Dict[str, Any]]:
    """模拟一次同步：行数增量增长、版本 v{n}+1、健康=healthy、更新同步时间。

    真实接入时替换为实际抽取/同步器，接口形态不变。
    """
    row = (db.query(DatasetAsset)
           .filter_by(id=dataset_id, company_id=company_id)
           .first())
    if not row:
        return None
    row.row_count = int((row.row_count or 0) * 1.07) + 3
    ver_n = 1
    if row.version.startswith("v") and row.version[1:].isdigit():
        ver_n = int(row.version[1:]) + 1
    row.version = f"v{ver_n}"
    row.health_status = "healthy"
    row.last_sync_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _asset_dict(row)


def dataset_lineage(db, company_id: int = 1) -> Dict[str, Any]:
    """血缘链视图（source → datasets，按 source 去重）。"""
    rows = (db.query(DatasetAsset)
            .filter_by(company_id=company_id)
            .order_by(DatasetAsset.id)
            .all())
    by_source: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_source.setdefault(r.source_id, []).append(_asset_dict(r))
    items = []
    for source_id, assets in by_source.items():
        src = get_source(source_id) or {}
        items.append({
            "source_id": source_id,
            "source_name": src.get("name", source_id),
            "source_status": src.get("status", ""),
            "datasets": assets,
        })
    return {"items": items, "total": len(items)}
