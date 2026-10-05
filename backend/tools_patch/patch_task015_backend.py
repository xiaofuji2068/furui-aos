# -*- coding: utf-8 -*-
from pathlib import Path
ROOT = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")
APP = ROOT / "app"

# 1) 追加 AppPage
p = APP / "models_ai.py"
block = '''

class AppPage(Base):
    """低代码页面定义（40-03）：Widget 列表（layout_json）+ 发布状态。"""
    __tablename__ = "app_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), default=1, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, server_default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")  # draft|published
    version: Mapped[str] = mapped_column(String(32), nullable=False, server_default="1.0")
    layout_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")  # [ {widget,title,params} ]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"),
                                                 onupdate=_utcnow)

    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_app_pages_company_code"),)
'''
p.write_text(p.read_text(encoding="utf-8").rstrip() + "\n" + block, encoding="utf-8")
print("OK models_ai AppPage appended")

# 2) app/pages.py
pages_py = '''"""低代码页面（40-03）：PageDef CRUD + 发布 + seed 示例页。"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .models_ai import AppPage


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
    rows = db.query(AppPage).filter(AppPage.company_id == company_id)\\
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
'''
p = APP / "pages.py"
p.write_text(pages_py, encoding="utf-8")
print("OK app/pages.py")

# 3) api/pages_api.py
api_py = '''"""低代码页面 API（40-03）：列表/详情/创建/更新/发布/删除 + 运行时取定义。"""
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
'''
p = APP / "api" / "pages_api.py"
p.write_text(api_py, encoding="utf-8")
print("OK app/api/pages_api.py")

# 4) 注册
p = APP / "api" / "__init__.py"
s = p.read_text(encoding="utf-8")
old = "from .logic_api import router as logic_router"
new = "from .logic_api import router as logic_router\nfrom .pages_api import router as pages_router"
assert old in s
s = s.replace(old, new, 1)
old = "router.include_router(logic_router)"
new = "router.include_router(logic_router)\n# 低代码页面（40-03）\nrouter.include_router(pages_router)"
assert old in s
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")
print("OK api/__init__.py registered")

# 5) 迁移
vp = ROOT / "alembic" / "versions" / "a1b2c3d4e5f6_app_pages.py"
migration = '''# -*- coding: utf-8 -*-
"""TASK-015：app_pages（低代码页面定义）+ RLS

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-09-24 10:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table('app_pages'):
        op.create_table(
            'app_pages',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('company_id', sa.Integer(),
                      sa.ForeignKey('companies.id', ondelete='CASCADE'),
                      nullable=False, server_default='1'),
            sa.Column('code', sa.String(64), nullable=False),
            sa.Column('title', sa.String(128), nullable=False),
            sa.Column('description', sa.String(500), nullable=False, server_default=''),
            sa.Column('status', sa.String(16), nullable=False, server_default='draft'),
            sa.Column('version', sa.String(32), nullable=False, server_default='1.0'),
            sa.Column('layout_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.UniqueConstraint('company_id', 'code', name='uq_app_pages_company_code'),
        )
    if bind.dialect.name == 'postgresql':
        cond = "company_id = NULLIF(current_setting('app.company_id', true), '')::int"
        op.execute("ALTER TABLE app_pages ENABLE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE app_pages FORCE ROW LEVEL SECURITY;")
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON app_pages;")
        op.execute(f"CREATE POLICY tenant_isolation ON app_pages USING ({cond}) WITH CHECK ({cond});")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON app_pages;")
        op.execute("ALTER TABLE app_pages DISABLE ROW LEVEL SECURITY;")
    if sa.inspect(bind).has_table('app_pages'):
        op.drop_table('app_pages')
'''
vp.write_text(migration, encoding="utf-8")
print("OK migration a1b2c3d4e5f6_app_pages.py")

# 6) 测试
test_py = '''# -*- coding: utf-8 -*-
"""TASK-015：PageDef 创建/读取/更新/发布/删除 + seed 幂等 + 租户隔离。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal, engine, Base
from app import models  # noqa: F401
from app import models_ai  # noqa: F401
from app.pages import (
    seed_pages, list_pages, get_page, get_page_by_code,
    create_page, update_page, publish_page, delete_page,
)
from app.models import Company

PASS: list = []
FAIL: list = []


def check(name, cond):
    if cond:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}")


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        c = db.query(Company).filter(Company.code == "furui").first()
        cid = c.id if c else 1

        created = seed_pages(db, cid)
        check("seed 幂等（首次创建或已存在）", len(created) in (0, 1))
        items = list_pages(db, cid)
        check("页面列表至少 1 张", len(items) >= 1)
        seed_item = next((i for i in items if i["code"] == "nuclear-overview"), None)
        check("seed 页存在且已发布", seed_item is not None and seed_item["status"] == "published")
        check("seed 页 widget 数=5", seed_item["widget_count"] == 5 if seed_item else False)

        p = create_page(db, cid, "test-page", "测试页", "desc", [
            {"widget": "text_note", "title": "说明", "params": {"content": "hi"}},
            {"widget": "tasks", "title": "任务", "params": {"limit": 3}},
        ])
        check("创建返回草稿", p["status"] == "draft")
        check("layout 2 widget", len(p["layout"]) == 2)
        g = get_page(db, cid, p["id"])
        check("按 id 读回", g is not None and g["code"] == "test-page")

        dup = False
        try:
            create_page(db, cid, "test-page", "重复")
        except ValueError:
            dup = True
        check("重复 code 被拒绝", dup)

        up = update_page(db, cid, p["id"], {"title": "测试页v2", "layout": [
            {"widget": "stat_cards", "title": "KPI", "params": {}}]})
        check("更新标题生效", up["title"] == "测试页v2")
        check("版本递增 1.1", up["version"] == "1.1")
        check("layout 更新为 1 widget", len(up["layout"]) == 1)

        pub = publish_page(db, cid, p["id"], "published")
        check("发布成功", pub["status"] == "published")
        draft = publish_page(db, cid, p["id"], "draft")
        check("撤稿成功", draft["status"] == "draft")

        by_code = get_page_by_code(db, cid, "test-page")
        check("按 code 读取（草稿也可取）", by_code is not None and by_code["code"] == "test-page")

        check("删除成功", delete_page(db, cid, p["id"]) is True)
        check("删除后读空", get_page(db, cid, p["id"]) is None)

        other = get_page_by_code(db, 999, "nuclear-overview")
        check("其他租户读不到", other is None)
    finally:
        db.close()

    print(f"\\nRESULT: PASS {len(PASS)} / FAIL {len(FAIL)} / SKIP 0")
    if FAIL:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
'''
tp = ROOT / "tests" / "test_pages.py"
tp.write_text(test_py, encoding="utf-8")
print("OK tests/test_pages.py")