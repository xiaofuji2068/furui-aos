"""低代码页面（40-03）：PageDef CRUD + 发布 + seed 示例页。"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .models_ai import AppPage
from .models import Company


# Widget 类型注册表（供前端构建器下拉与运行时渲染）
WIDGET_TYPES = {
    "stat_cards": {"label": "统计卡片", "desc": "企业总览 KPI（/api/overview）", "default_params": {}},
    "object_list": {"label": "对象列表", "desc": "本体图实体列表（对象中心数据）", "default_params": {"type": "All"}},
    "data_assets": {"label": "数据资产", "desc": "数据资产表格（/api/data-assets）", "default_params": {}},
    "tasks": {"label": "最近任务", "desc": "任务列表（/api/tasks）", "default_params": {"limit": 8}},
    "text_note": {"label": "文本说明", "desc": "静态说明文字", "default_params": {"content": "在这里输入说明文字"}},
}


def _default_page() -> Dict[str, Any]:
    return {
        "code": "nuclear-overview",
        "title": "核电巡检总览",
        "description": "示例低代码页：监测站/巡检任务/数据资产一屏概览（TASK-015 seed，可编辑）",
        "layout": [
            {"widget": "text_note", "title": "巡检指挥台", "params": {"content": "本页由低代码构建器生成：统计卡片 → 对象列表 → 最近任务 → 数据资产。"}},
            {"widget": "stat_cards", "title": "核心指标", "params": {}},
            {"widget": "object_list", "title": "监测对象", "params": {"type": "All"}},
            {"widget": "tasks", "title": "最近任务", "params": {"limit": 6}},
            {"widget": "data_assets", "title": "数据资产", "params": {}},
        ],
    }


def seed_pages(db: Session, company_id: int = 1) -> List[AppPage]:
    created: List[AppPage] = []
    if db.get(Company, company_id) is None:
        return created  # 无效租户：不 seed（外键/RLS 防御）
    d = _default_page()
    exists = db.query(AppPage).filter(AppPage.company_id == company_id,
                                      AppPage.code == d["code"]).first()
    if not exists:
        pg = AppPage(company_id=company_id, code=d["code"], title=d["title"],
                     description=d["description"], status="published", version="1.0",
                     layout_json=json.dumps(d["layout"], ensure_ascii=False))
        db.add(pg)
        db.commit()
        db.refresh(pg)
        created.append(pg)
    return created


def list_pages(db: Session, company_id: int) -> List[Dict[str, Any]]:
    seed_pages(db, company_id)
    rows = db.query(AppPage).filter(AppPage.company_id == company_id)\
        .order_by(AppPage.id).all()
    return [{
        "id": p.id, "code": p.code, "title": p.title, "description": p.description,
        "status": p.status, "version": p.version,
        "widget_count": len(_parse_layout(p.layout_json)),
        "updated_at": p.updated_at.isoformat() if p.updated_at else "",
    } for p in rows]


def get_page(db: Session, company_id: int, page_id: int) -> Optional[Dict[str, Any]]:
    p = db.query(AppPage).filter(AppPage.id == page_id,
                                 AppPage.company_id == company_id).first()
    if not p:
        return None
    return _to_dict(p)


def get_page_by_code(db: Session, company_id: int, code: str) -> Optional[Dict[str, Any]]:
    seed_pages(db, company_id)
    p = db.query(AppPage).filter(AppPage.company_id == company_id,
                                 AppPage.code == code).first()
    if not p:
        return None
    return _to_dict(p)


def create_page(db: Session, company_id: int, code: str, title: str,
                description: str = "", layout: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    if db.query(AppPage).filter(AppPage.company_id == company_id,
                                AppPage.code == code).first():
        raise ValueError(f"code '{code}' 已存在")
    p = AppPage(company_id=company_id, code=code, title=title,
                description=description, status="draft", version="1.0",
                layout_json=json.dumps(layout or [], ensure_ascii=False))
    db.add(p)
    db.commit()
    db.refresh(p)
    return _to_dict(p)


def update_page(db: Session, company_id: int, page_id: int,
                patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    p = db.query(AppPage).filter(AppPage.id == page_id,
                                 AppPage.company_id == company_id).first()
    if not p:
        return None
    if "title" in patch and patch["title"] is not None:
        p.title = str(patch["title"])
    if "description" in patch and patch["description"] is not None:
        p.description = str(patch["description"])
    if "layout" in patch and patch["layout"] is not None:
        p.layout_json = json.dumps(patch["layout"], ensure_ascii=False)
        p.version = _bump(p.version)
    db.commit()
    db.refresh(p)
    return _to_dict(p)


def publish_page(db: Session, company_id: int, page_id: int,
                 status: str = "published") -> Optional[Dict[str, Any]]:
    p = db.query(AppPage).filter(AppPage.id == page_id,
                                 AppPage.company_id == company_id).first()
    if not p:
        return None
    p.status = status if status in ("published", "draft") else "published"
    db.commit()
    db.refresh(p)
    return _to_dict(p)


def delete_page(db: Session, company_id: int, page_id: int) -> bool:
    p = db.query(AppPage).filter(AppPage.id == page_id,
                                 AppPage.company_id == company_id).first()
    if not p:
        return False
    db.delete(p)
    db.commit()
    return True


def _to_dict(p: AppPage) -> Dict[str, Any]:
    return {
        "id": p.id, "code": p.code, "title": p.title, "description": p.description,
        "status": p.status, "version": p.version,
        "layout": _parse_layout(p.layout_json),
        "created_at": p.created_at.isoformat() if p.created_at else "",
        "updated_at": p.updated_at.isoformat() if p.updated_at else "",
    }


def _parse_layout(raw: str) -> List[Dict[str, Any]]:
    try:
        v = json.loads(raw or "[]")
        return v if isinstance(v, list) else []
    except (TypeError, ValueError):
        return []


def _bump(version: str) -> str:
    try:
        major, minor = (version or "1.0").split(".")
        return f"{major}.{int(minor) + 1}"
    except (ValueError, AttributeError):
        return "1.0"
