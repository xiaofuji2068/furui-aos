# -*- coding: utf-8 -*-
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
        c = db.query(Company).order_by(Company.id).first()
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

    print(f"\nRESULT: PASS {len(PASS)} / FAIL {len(FAIL)} / SKIP 0")
    if FAIL:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
