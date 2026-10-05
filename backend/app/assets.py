"""资产装配（50 全系）：Bundle 目录 / Manifest / 派生安装（Derive-first）/ Resolver / seed。

语义（用户 2026-09-27 拍板"派生优先"）：
- Bundle 是系统级资产目录（RLS 豁免，类似 permissions/ontology_types 先例），记录作者 created_by_company_id。
- 租户安装 = 把 Bundle 内容复制到租户命名空间生成派生资产（app_pages / logic_graphs），原 Bundle 只读。
- 同 code 派生资产已存在（可能被租户定制过）→ 跳过创建、记录引用（保留定制）；rederive 显式补齐缺失。
- Bundle 升级（version 变化）→ 重装时补齐缺失派生资产，不覆盖租户已有定制。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .models import Company
from .models_ai import AssetBundle, AssetInstallation, AppPage, LogicGraph, LogicNode

BUNDLE_KINDS = {"bundle", "plugin"}


# ---------- 内置 Bundle 定义（与 TASK-015/014 种子资产同源，派生给各租户） ----------

def _default_bundles() -> List[Dict[str, Any]]:
    from . import mainline  # 运行时导入避免循环依赖

    def _graph_nodes(plan) -> List[Dict[str, Any]]:
        return [{
            "seq": p["seq"],
            "key": f"step_{p['seq']}",
            "title": p["title"],
            "kind": p["kind"],
            "tool": p.get("tool", ""),
            "label": p["title"],
            "params": p.get("params", {}),
            "depends": p.get("depends", []),
        } for p in plan]

    return [
        {
            "code": "nuclear-inspection-bundle",
            "name": "核电巡检总览",
            "description": "核电巡检一屏概览：KPI + 监测对象 + 最近任务 + 数据资产，附巡检异常归因链路。",
            "version": "1.0",
            "kind": "bundle",
            "manifest": {
                "nav_entry": {"href": "/pages/nuclear-overview", "icon": "☢️",
                              "label": "核电巡检总览", "perm": "tool:config"},
                "widget_types": [],
                "permissions": ["tool:config"],
                "requires": ["pages", "logic"],
            },
            "content": {
                "pages": [{
                    "code": "nuclear-overview",
                    "title": "核电巡检总览",
                    "description": "示例低代码页：监测站/巡检任务/数据资产一屏概览（Bundle 派生，可编辑）。",
                    "layout": [
                        {"widget": "text_note", "title": "巡检指挥台",
                         "params": {"content": "本页由资产 Bundle 派生安装：统计卡片 → 对象列表 → 最近任务 → 数据资产。"}},
                        {"widget": "stat_cards", "title": "核心指标", "params": {}},
                        {"widget": "object_list", "title": "监测对象", "params": {"type": "All"}},
                        {"widget": "tasks", "title": "最近任务", "params": {"limit": 6}},
                        {"widget": "data_assets", "title": "数据资产", "params": {}},
                    ],
                }],
                "logic_graphs": [{
                    "code": "inspection-anomaly",
                    "name": "核电巡检异常归因链路",
                    "description": "监测站 → 指标 → 知识 → 归因 → 报告 → 工单审批（Bundle 派生，可编辑）",
                    "nodes": _graph_nodes(mainline.PLAN_INSPECTION),
                }],
            },
        },
        {
            "code": "sales-command-bundle",
            "name": "销售经营看板",
            "description": "销售 KPI + 跟进任务 + 数据资产一屏看板，附销售下降归因链路。",
            "version": "1.0",
            "kind": "bundle",
            "manifest": {
                "nav_entry": {"href": "/pages/sales-command", "icon": "📊",
                              "label": "销售经营看板", "perm": "tool:config"},
                "widget_types": [],
                "permissions": ["tool:config"],
                "requires": ["pages", "logic"],
            },
            "content": {
                "pages": [{
                    "code": "sales-command",
                    "title": "销售经营看板",
                    "description": "销售 KPI / 跟进任务 / 数据资产一屏看板（Bundle 派生，可编辑）。",
                    "layout": [
                        {"widget": "text_note", "title": "销售指挥台",
                         "params": {"content": "本页由资产 Bundle 派生安装：核心指标 → 销售任务 → 数据资产。"}},
                        {"widget": "stat_cards", "title": "核心指标", "params": {}},
                        {"widget": "tasks", "title": "销售跟进任务", "params": {"limit": 8}},
                        {"widget": "data_assets", "title": "数据资产", "params": {}},
                    ],
                }],
                "logic_graphs": [{
                    "code": "sales-drop",
                    "name": "销售下降归因链路",
                    "description": "ERP → CRM → 知识 → 归因 → 报告 → 审批动作（Bundle 派生，可编辑）",
                    "nodes": _graph_nodes(mainline.PLAN),
                }],
            },
        },
    ]


def seed_bundles(db: Session) -> List[AssetBundle]:
    """幂等 seed：系统 Bundle 目录（code 唯一，不覆盖已发布/已修改的 Bundle）。"""
    created: List[AssetBundle] = []
    for d in _default_bundles():
        exists = db.query(AssetBundle).filter(AssetBundle.code == d["code"]).first()
        if exists:
            continue
        b = AssetBundle(
            code=d["code"], name=d["name"], description=d["description"],
            version=d["version"], kind=d["kind"],
            manifest_json=json.dumps(d["manifest"], ensure_ascii=False),
            content_json=json.dumps(d["content"], ensure_ascii=False),
            status="published", created_by_company_id=1,
        )
        db.add(b)
        created.append(b)
    if created:
        db.commit()
    return created


# ---------- Catalog（Registry） ----------

def _safe_json(raw: str, fallback: Any) -> Any:
    try:
        return json.loads(raw or "{}")
    except Exception:
        return fallback


def _bundle_to_dict(b: AssetBundle, installed: bool = False,
                    install: Optional[AssetInstallation] = None) -> Dict[str, Any]:
    manifest = _safe_json(b.manifest_json, {})
    content = _safe_json(b.content_json, {})
    nav = manifest.get("nav_entry", {})
    return {
        "id": b.id,
        "code": b.code,
        "name": b.name,
        "description": b.description,
        "version": b.version,
        "kind": b.kind,
        "status": b.status,
        "manifest": manifest,
        "nav_entry": nav,
        "page_codes": [p.get("code") for p in content.get("pages", [])],
        "graph_codes": [g.get("code") for g in content.get("logic_graphs", [])],
        "created_by_company_id": b.created_by_company_id,
        "created_at": b.created_at.isoformat() if b.created_at else "",
        "installed": installed,
        "installation": {
            "id": install.id, "status": install.status,
            "bundle_version": install.bundle_version,
            "derived_pages": _safe_json(install.derived_pages_json, []),
            "derived_graphs": _safe_json(install.derived_graphs_json, []),
            "installed_at": install.installed_at.isoformat() if install.installed_at else "",
        } if install else None,
    }


def list_bundles(db: Session, company_id: Optional[int] = None) -> List[Dict[str, Any]]:
    seed_bundles(db)
    rows = db.query(AssetBundle).order_by(AssetBundle.id).all()
    install_map = {}
    if company_id:
        install_map = {i.bundle_id: i for i in db.query(AssetInstallation)
                       .filter(AssetInstallation.company_id == company_id,
                               AssetInstallation.status == "installed").all()}
    return [_bundle_to_dict(b, b.id in install_map, install_map.get(b.id)) for b in rows]


def get_bundle(db: Session, bundle_id: int, company_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    b = db.get(AssetBundle, bundle_id)
    if not b:
        return None
    install = None
    if company_id:
        install = db.query(AssetInstallation).filter(
            AssetInstallation.company_id == company_id,
            AssetInstallation.bundle_id == b.id,
            AssetInstallation.status == "installed").first()
    return _bundle_to_dict(b, install is not None, install)


def create_bundle(db: Session, data: Dict[str, Any],
                  created_by_company_id: int = 1) -> AssetBundle:
    """创建 Bundle（Manifest 校验：requires 与 content 一致）。"""
    code = (data.get("code") or "").strip()
    name = (data.get("name") or "").strip()
    if not code or not name:
        raise ValueError("code/name 必填")
    if db.query(AssetBundle).filter(AssetBundle.code == code).first():
        raise ValueError(f"Bundle code '{code}' 已存在")
    manifest = data.get("manifest") or {}
    content = data.get("content") or {}
    requires = manifest.get("requires", [])
    if "pages" in requires and not content.get("pages"):
        raise ValueError("manifest.requires 声明 pages，但 content.pages 为空")
    if "logic" in requires and not content.get("logic_graphs"):
        raise ValueError("manifest.requires 声明 logic，但 content.logic_graphs 为空")
    b = AssetBundle(
        code=code, name=name,
        description=(data.get("description") or "").strip(),
        version=(data.get("version") or "1.0").strip(),
        kind=data.get("kind", "bundle") if data.get("kind", "bundle") in BUNDLE_KINDS else "bundle",
        manifest_json=json.dumps(manifest, ensure_ascii=False),
        content_json=json.dumps(content, ensure_ascii=False),
        status="draft",
        created_by_company_id=created_by_company_id,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


def publish_bundle(db: Session, bundle_id: int) -> Optional[AssetBundle]:
    b = db.get(AssetBundle, bundle_id)
    if not b:
        return None
    b.status = "published"
    db.commit()
    db.refresh(b)
    return b


# ---------- Installation（派生优先） ----------

def _derive_page(db: Session, company_id: int, bundle: AssetBundle,
                 pg: Dict[str, Any]) -> Dict[str, Any]:
    """派生页面：租户已有同 code 页面（可能定制过）→ 跳过创建并引用现有；否则创建并发布。"""
    code = pg["code"]
    existing = db.query(AppPage).filter(AppPage.company_id == company_id,
                                        AppPage.code == code).first()
    if existing:
        return {"code": code, "page_id": existing.id, "title": existing.title, "reused": True}
    page = AppPage(company_id=company_id, code=code, title=pg["title"],
                   description=pg.get("description", ""),
                   status="published", version=bundle.version,
                   layout_json=json.dumps(pg.get("layout", []), ensure_ascii=False))
    db.add(page)
    db.flush()
    return {"code": code, "page_id": page.id, "title": page.title, "reused": False}


def _derive_graph(db: Session, company_id: int, bundle: AssetBundle,
                  g: Dict[str, Any]) -> Dict[str, Any]:
    """派生 Logic 图：租户已有同 code 图 → 跳过创建并引用现有；否则建图+节点。"""
    code = g["code"]
    existing = db.query(LogicGraph).filter(LogicGraph.company_id == company_id,
                                           LogicGraph.code == code).first()
    if existing:
        return {"code": code, "graph_id": existing.id, "name": existing.name, "reused": True}
    graph = LogicGraph(company_id=company_id, code=code, name=g["name"],
                       version=bundle.version, description=g.get("description", ""),
                       status="active")
    db.add(graph)
    db.flush()
    for nd in g.get("nodes", []):
        db.add(LogicNode(graph_id=graph.id, company_id=company_id,
                         seq=nd["seq"], key=nd.get("key", f"step_{nd['seq']}"),
                         title=nd["title"], kind=nd["kind"], tool=nd.get("tool", ""),
                         label=nd.get("label", nd["title"]),
                         params_json=json.dumps(nd.get("params", {}), ensure_ascii=False),
                         depends_json=json.dumps(nd.get("depends", []), ensure_ascii=False)))
    return {"code": code, "graph_id": graph.id, "name": graph.name, "reused": False}


def install_bundle(db: Session, company_id: int, bundle_id: int) -> Dict[str, Any]:
    """派生安装（幂等）：已装 → 补齐缺失派生资产并更新版本；未装 → 全量派生。"""
    b = db.get(AssetBundle, bundle_id)
    if not b:
        raise ValueError("bundle not found")
    if b.status != "published":
        raise ValueError("Bundle 未发布，不能安装")
    if db.get(Company, company_id) is None:
        raise ValueError("invalid tenant")
    content = _safe_json(b.content_json, {})
    install = db.query(AssetInstallation).filter(
        AssetInstallation.company_id == company_id,
        AssetInstallation.bundle_id == b.id).first()
    is_new = install is None
    if not install:
        install = AssetInstallation(company_id=company_id, bundle_id=b.id,
                                    bundle_code=b.code, bundle_version=b.version,
                                    status="installed")
        db.add(install)
        db.flush()

    # 派生 pages / logic_graphs（同 code 已存在 → 复用，保留租户定制）
    derived_pages = _safe_json(install.derived_pages_json, [])
    derived_graphs = _safe_json(install.derived_graphs_json, [])
    page_codes = {p["code"] for p in derived_pages}
    graph_codes = {g["code"] for g in derived_graphs}
    for pg in content.get("pages", []):
        if pg["code"] not in page_codes:
            rec = _derive_page(db, company_id, b, pg)
            derived_pages.append(rec)
            page_codes.add(rec["code"])
    for g in content.get("logic_graphs", []):
        if g["code"] not in graph_codes:
            rec = _derive_graph(db, company_id, b, g)
            derived_graphs.append(rec)
            graph_codes.add(rec["code"])

    install.bundle_version = b.version
    install.derived_pages_json = json.dumps(derived_pages, ensure_ascii=False)
    install.derived_graphs_json = json.dumps(derived_graphs, ensure_ascii=False)
    db.commit()
    db.refresh(install)
    return {
        "installation_id": install.id,
        "bundle": {"id": b.id, "code": b.code, "name": b.name, "version": b.version},
        "status": install.status,
        "created": is_new,
        "derived_pages": derived_pages,
        "derived_graphs": derived_graphs,
    }


def rederive_bundle(db: Session, company_id: int, installation_id: int) -> Dict[str, Any]:
    """显式重新派生：对照 Bundle 声明与租户 DB 中实际存在的派生资产，
    补齐缺失（已存在则引用现有、保留定制；记录过期不影响判断）。"""
    install = db.query(AssetInstallation).filter(
        AssetInstallation.id == installation_id,
        AssetInstallation.company_id == company_id,
        AssetInstallation.status == "installed").first()
    if not install:
        raise ValueError("installation not found")
    b = db.get(AssetBundle, install.bundle_id)
    if not b:
        raise ValueError("bundle not found")
    content = _safe_json(b.content_json, {})
    page_defs = content.get("pages", [])
    graph_defs = content.get("logic_graphs", [])

    def _actual_codes(model, codes: List[str]) -> set:
        if not codes:
            return set()
        return {r.code for r in db.query(model).filter(
            model.company_id == company_id, model.code.in_(codes)).all()}

    actual_pages = _actual_codes(AppPage, [p["code"] for p in page_defs])
    actual_graphs = _actual_codes(LogicGraph, [g["code"] for g in graph_defs])

    derived_pages: List[Dict[str, Any]] = []
    derived_graphs: List[Dict[str, Any]] = []
    added = {"pages": [], "graphs": []}
    for pg in page_defs:
        if pg["code"] in actual_pages:
            ex = db.query(AppPage).filter(AppPage.company_id == company_id,
                                          AppPage.code == pg["code"]).first()
            derived_pages.append({"code": ex.code, "page_id": ex.id,
                                  "title": ex.title, "reused": True})
        else:
            rec = _derive_page(db, company_id, b, pg)
            derived_pages.append(rec)
            added["pages"].append(rec)
    for g in graph_defs:
        if g["code"] in actual_graphs:
            ex = db.query(LogicGraph).filter(LogicGraph.company_id == company_id,
                                             LogicGraph.code == g["code"]).first()
            derived_graphs.append({"code": ex.code, "graph_id": ex.id,
                                   "name": ex.name, "reused": True})
        else:
            rec = _derive_graph(db, company_id, b, g)
            derived_graphs.append(rec)
            added["graphs"].append(rec)
    install.bundle_version = b.version
    install.derived_pages_json = json.dumps(derived_pages, ensure_ascii=False)
    install.derived_graphs_json = json.dumps(derived_graphs, ensure_ascii=False)
    db.commit()
    return {"installation_id": install.id, "bundle_version": b.version, "added": added,
            "derived_pages": derived_pages, "derived_graphs": derived_graphs}


def uninstall_bundle(db: Session, company_id: int, installation_id: int) -> Dict[str, Any]:
    """卸载：删除本租户派生资产（app_pages / logic_graphs），保留其他租户。"""
    install = db.query(AssetInstallation).filter(
        AssetInstallation.id == installation_id,
        AssetInstallation.company_id == company_id).first()
    if not install:
        raise ValueError("installation not found")
    derived_pages = _safe_json(install.derived_pages_json, [])
    derived_graphs = _safe_json(install.derived_graphs_json, [])
    for p in derived_pages:
        db.query(AppPage).filter(AppPage.company_id == company_id,
                                 AppPage.id == p.get("page_id")).delete()
    for g in derived_graphs:
        db.query(LogicNode).filter(LogicNode.company_id == company_id,
                                   LogicNode.graph_id == g.get("graph_id")).delete()
        db.query(LogicGraph).filter(LogicGraph.company_id == company_id,
                                    LogicGraph.id == g.get("graph_id")).delete()
    db.query(AssetInstallation).filter(AssetInstallation.id == install.id).delete()
    db.commit()
    return {"ok": True, "removed_pages": len(derived_pages), "removed_graphs": len(derived_graphs)}


# ---------- Resolver / Runtime ----------

def resolve_bundle(db: Session, company_id: int, bundle_code: str) -> Optional[Dict[str, Any]]:
    """Resolver：按 code 解析租户已装 Bundle 的派生资产（页面/图引用）。"""
    b = db.query(AssetBundle).filter(AssetBundle.code == bundle_code).first()
    if not b:
        return None
    install = db.query(AssetInstallation).filter(
        AssetInstallation.company_id == company_id,
        AssetInstallation.bundle_id == b.id,
        AssetInstallation.status == "installed").first()
    if not install:
        return None
    return {
        "bundle": {"id": b.id, "code": b.code, "name": b.name, "version": b.version},
        "derived_pages": _safe_json(install.derived_pages_json, []),
        "derived_graphs": _safe_json(install.derived_graphs_json, []),
    }


def installed_assets(db: Session, company_id: int) -> List[Dict[str, Any]]:
    """当前租户已安装 Bundle 列表（含派生引用）。"""
    seed_bundles(db)
    installs = db.query(AssetInstallation).filter(
        AssetInstallation.company_id == company_id,
        AssetInstallation.status == "installed").order_by(AssetInstallation.id).all()
    out = []
    for i in installs:
        b = db.get(AssetBundle, i.bundle_id)
        if not b:
            continue
        manifest = _safe_json(b.manifest_json, {})
        out.append({
            "installation_id": i.id,
            "bundle": {"id": b.id, "code": b.code, "name": b.name, "version": b.version},
            "nav_entry": manifest.get("nav_entry", {}),
            "derived_pages": _safe_json(i.derived_pages_json, []),
            "derived_graphs": _safe_json(i.derived_graphs_json, []),
            "installed_at": i.installed_at.isoformat() if i.installed_at else "",
        })
    return out


def installed_nav(db: Session, company_id: int) -> List[Dict[str, Any]]:
    """侧边栏动态入口（Plugin 轻量落地）：已装 Bundle 的 nav_entry + 派生页可访问性。"""
    out = []
    for a in installed_assets(db, company_id):
        nav = a.get("nav_entry") or {}
        if not nav.get("href"):
            continue
        href = nav["href"]
        # 页面入口：href 指向 /pages/{code} 时校验派生页存在
        if href.startswith("/pages/"):
            code = href.rsplit("/", 1)[-1]
            if not any(p.get("code") == code for p in a["derived_pages"]):
                continue
        out.append({"href": href, "icon": nav.get("icon", "📦"),
                    "label": nav.get("label", a["bundle"]["name"]),
                    "perm": nav.get("perm", "tool:config"),
                    "bundle": a["bundle"]["code"]})
    return out
