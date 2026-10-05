# -*- coding: utf-8 -*-
"""TASK-016：Bundle 目录 seed / Manifest 校验 / 派生安装（幂等）/ 跨租户隔离 / rederive / 卸载 / Resolver / nav。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal, engine, Base, DATABASE_URL, IS_SQLITE
from sqlalchemy import create_engine
from app import models  # noqa: F401
from app import models_ai  # noqa: F401
from app.assets import (
    seed_bundles, list_bundles, get_bundle, create_bundle, publish_bundle,
    install_bundle, rederive_bundle, uninstall_bundle,
    resolve_bundle, installed_assets, installed_nav,
)
from app.models import Company
from app.models_ai import AssetBundle, AssetInstallation, AppPage, LogicGraph, LogicNode

PASS: list = []
FAIL: list = []


def check(name, cond, extra: str = ""):
    if cond:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}" + (f"  <{extra}>" if extra else ""))


def _create_all():
    """SQLite 3.53 + db.py FK=ON + 延迟事务下，create_all 事务内 CREATE INDEX 会误报
    'no such table: main.data_datasets'（环境级坑，与业务代码无关）。
    用无 FK 事件的临时引擎建表绕过；PG 直接 create_all。"""
    if IS_SQLITE:
        tmp = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=tmp)
        tmp.dispose()
    else:
        Base.metadata.create_all(bind=engine)


def main():
    _create_all()
    db = SessionLocal()
    try:
        c = db.query(Company).order_by(Company.id).first()
        cid = c.id if c else 1
        other = 999  # 模拟另一租户（不存在的 company：无派生可见）

        # 0) 清掉本测试上一轮留下的痕迹：Bundle 实体 + 安装记录。
        #    这个脚本从 TASK-016 起就只靠「每次重置测试库」才跑得绿
        #    （否则第二次跑必撞 Bundle code 已存在），回归里表现为「第一次绿、
        #    第二次红」的假故障。这里补上自清理，让它自己就能复跑。
        #    默认 bundle 也一并删掉：seed_bundles 是幂等 seed，会原地重建。
        #    清单要覆盖本脚本 create_bundle 用过的每一个 code，漏一个就换个地方崩。
        touched = ("test-bundle", "draft-bundle", "bad-bundle", "nuclear-inspection-bundle")
        db.query(AssetInstallation).filter(
            AssetInstallation.bundle_code.in_(touched)).delete(synchronize_session=False)
        db.query(AssetBundle).filter(AssetBundle.code.in_(touched)).delete(
            synchronize_session=False)
        db.commit()

        # 1) seed 幂等
        # 注意口径：seed_bundles 是幂等的「已存在则跳过」，返回值是**本次新建**数，
        # 不是「目录里的总条数」。可能取值：
        #   0 = 默认 Bundle 都已在（已 init 的库，最常见）
        #   1 = 上面第 0 段删掉过某个默认 Bundle，本轮重建它
        #   2 = 完全空库首次 seed
        # 写死 ==2 是这条测试长期假红的老根（曾误判为「生产库状态耦合」）。
        created = seed_bundles(db)
        check("seed 幂等（返回本次新建数，0/1/2 均合法）", len(created) in (0, 1, 2),
              f"created={len(created)}")
        # 幂等的真正语义是「重复 seed 不新增」，不是「数量恒等于 2」：
        # 库里可能有其它测试造的 Bundle（如 test-bundle），写死 2 会随残留而红。
        before_n = db.query(AssetBundle).count()
        seed_bundles(db)
        after_n = db.query(AssetBundle).count()
        check("seed 幂等（重复不新增）", after_n == before_n, f"{before_n} -> {after_n}")
        nb = db.query(AssetBundle).filter(AssetBundle.code == "nuclear-inspection-bundle").first()
        check("核电 Bundle 存在且已发布", nb is not None and nb.status == "published")
        check("核电 Bundle manifest 有 nav_entry",
              nb is not None and "nav_entry" in __import__("json").loads(nb.manifest_json))

        # 2) catalog 列表 + 安装状态
        # 只断言「默认 Bundle 未被装」，不能断言 all(installed=False)：
        # 别的测试可能已装过某个 Bundle，all() 口径会把干净前提偷偷假设进来。
        items = list_bundles(db, cid)
        check("catalog 至少 2 条", len(items) >= 2)
        installed_codes = {i["code"] for i in items if i.get("installed")}
        check("catalog 未安装标记（默认 Bundle 未被装）",
              "nuclear-inspection-bundle" not in installed_codes, str(sorted(installed_codes)))

        # 3) 创建 Bundle + Manifest 校验
        bad = False
        try:
            create_bundle(db, {"code": "bad-bundle", "name": "坏包",
                               "manifest": {"requires": ["pages"]}, "content": {}}, cid)
        except ValueError:
            bad = True
        check("requires pages 但 content 为空被拒", bad)
        b = create_bundle(db, {
            "code": "test-bundle", "name": "测试包", "description": "d",
            "version": "1.0", "kind": "bundle",
            "manifest": {"nav_entry": {"href": "/pages/test-b", "icon": "🧪",
                                        "label": "测试入口", "perm": "tool:config"},
                         "requires": ["pages", "logic"]},
            "content": {
                "pages": [{"code": "test-b", "title": "测试页", "description": "d",
                           "layout": [{"widget": "text_note", "title": "T", "params": {"content": "hi"}}]}],
                "logic_graphs": [{"code": "test-graph", "name": "测试图", "description": "d",
                                  "nodes": [{"seq": 1, "title": "步骤1", "kind": "tool",
                                             "tool": "data.fetch", "params": {}, "depends": []}]}],
            },
        }, cid)
        check("创建 Bundle 为 draft", b.status == "draft")
        check("创建 Bundle 记录作者租户", b.created_by_company_id == cid)
        dup = False
        try:
            create_bundle(db, {"code": "test-bundle", "name": "重复"}, cid)
        except ValueError:
            dup = True
        check("重复 Bundle code 被拒", dup)
        pub = publish_bundle(db, b.id)
        check("发布成功", pub is not None and pub.status == "published")

        # 4) 安装（派生页面 + logic 图）
        r = install_bundle(db, cid, b.id)
        check("安装返回派生 1 页 + 1 图", len(r["derived_pages"]) == 1 and len(r["derived_graphs"]) == 1)
        check("首次安装 created=True", r["created"] is True)
        page = db.query(AppPage).filter(AppPage.company_id == cid, AppPage.code == "test-b").first()
        check("派生页面已创建且发布", page is not None and page.status == "published")
        check("派生页面版本=Bundle 版本", page is not None and page.version == "1.0")
        graph = db.query(LogicGraph).filter(LogicGraph.company_id == cid, LogicGraph.code == "test-graph").first()
        check("派生 Logic 图已创建且 active", graph is not None and graph.status == "active")
        nodes = db.query(LogicNode).filter(LogicNode.graph_id == graph.id).count()
        check("派生图节点=1", nodes == 1)

        # 5) 安装幂等（重复安装不重复派生）
        r2 = install_bundle(db, cid, b.id)
        check("重复安装 created=False", r2["created"] is False)
        check("重复安装不新增派生页", db.query(AppPage).filter(
            AppPage.company_id == cid, AppPage.code == "test-b").count() == 1)

        # 6) 跨租户隔离
        other_view = list_bundles(db, other)
        check("其他租户看不到安装状态", all(not i["installed"] for i in other_view))
        check("其他租户读不到派生页", db.query(AppPage).filter(
            AppPage.company_id == other, AppPage.code == "test-b").count() == 0)
        check("其他租户 resolve 为 None", resolve_bundle(db, other, "test-bundle") is None)

        # 7) rederive：删除派生后补齐
        db.query(LogicNode).filter(LogicNode.graph_id == graph.id).delete()
        db.query(LogicGraph).filter(LogicGraph.id == graph.id).delete()
        db.commit()
        rd = rederive_bundle(db, cid, r["installation_id"])
        check("rederive 补齐缺失图", len(rd["added"]["graphs"]) == 1)
        check("rederive 补齐后图存在", db.query(LogicGraph).filter(
            LogicGraph.company_id == cid, LogicGraph.code == "test-graph").count() == 1)
        check("rederive 不重复补已存在页", len(rd["added"]["pages"]) == 0)

        # 8) 同 code 复用（租户已有页面保留定制）
        r3 = install_bundle(db, cid, nb.id)
        check("核电 Bundle 安装成功", r3["created"] is True)
        # 生产已有 nuclear-overview（TASK-015 seed）→ 复用 not reused 应为 False
        # 测试库无 → 派生创建
        check("核电 Bundle 派生页已存在", db.query(AppPage).filter(
            AppPage.company_id == cid, AppPage.code == "nuclear-overview").count() >= 1)

        # 9) installed_assets / installed_nav
        installed = installed_assets(db, cid)
        check("installed 列表 2 条", len(installed) == 2)
        nav = installed_nav(db, cid)
        check("installed_nav 返回派生页入口", any(n["href"].endswith("nuclear-overview") for n in nav))

        # 10) 卸载：删除派生资产 + 记录
        un = uninstall_bundle(db, cid, r["installation_id"])
        check("卸载返回移除 1 页 1 图", un["removed_pages"] == 1 and un["removed_graphs"] == 1)
        check("卸载后派生页已删", db.query(AppPage).filter(
            AppPage.company_id == cid, AppPage.code == "test-b").count() == 0)
        check("卸载后安装记录已删", db.query(AssetInstallation).filter(
            AssetInstallation.id == r["installation_id"]).count() == 0)
        check("卸载后 resolve 为 None", resolve_bundle(db, cid, "test-bundle") is None)
        check("卸载不影响其他 Bundle", db.query(AssetInstallation).filter(
            AssetInstallation.company_id == cid).count() == 1)

        # 11) 未发布 Bundle 不可安装
        bd = create_bundle(db, {"code": "draft-bundle", "name": "草稿包",
                                "manifest": {}, "content": {}}, cid)
        notpub = False
        try:
            install_bundle(db, cid, bd.id)
        except ValueError:
            notpub = True
        check("未发布 Bundle 安装被拒", notpub)
    finally:
        db.close()

    print(f"\nRESULT: PASS {len(PASS)} / FAIL {len(FAIL)} / SKIP 0")
    if FAIL:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
