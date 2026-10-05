"""Logic 决策编排图（30-03）：服务端图存储 / seed / 读图执行。

目标：把硬编码在 mainline.PLAN / PLAN_INSPECTION 的编排提升为"数据态"——
图定义存 DB，可查 / 可编辑节点 / 可切换激活；执行引擎读 active 图运行。
工具实现（每个 tool 的参数/输出处理）仍是代码，但"图结构"（步骤/顺序/依赖/参数）是数据。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .models_ai import LogicGraph, LogicNode


# ---------- 图定义（默认种子：与 mainline.PLAN / PLAN_INSPECTION 完全一致） ----------

def _default_graphs() -> List[Dict[str, Any]]:
    from . import mainline  # 运行时导入避免循环依赖

    out = []
    for code, name, desc, plan in [
        ("sales-drop", "销售下降归因链路", "ERP → CRM → 知识 → 归因 → 报告 → 审批动作（销售主链路）", mainline.PLAN),
        ("inspection-anomaly", "核电巡检异常归因链路", "监测站 → 指标 → 知识 → 归因 → 报告 → 工单审批（核电主链路）", mainline.PLAN_INSPECTION),
    ]:
        nodes = []
        for p in plan:
            nodes.append({
                "seq": p["seq"],
                "key": f"step_{p['seq']}",
                "title": p["title"],
                "kind": p["kind"],
                "tool": p.get("tool", ""),
                "label": p["title"],
                "params_json": json.dumps(p.get("params", {}), ensure_ascii=False),
                "depends_json": json.dumps(p.get("depends", []), ensure_ascii=False),
            })
        out.append({"code": code, "name": name, "description": desc, "nodes": nodes})
    return out


def seed_graphs(db: Session, company_id: int = 1) -> List[LogicGraph]:
    """幂等 seed：把默认链路写入 DB（不覆盖已存在的 active 图）。"""
    created: List[LogicGraph] = []
    for g in _default_graphs():
        exists = db.query(LogicGraph).filter(
            LogicGraph.company_id == company_id, LogicGraph.code == g["code"]).first()
        if exists:
            continue
        graph = LogicGraph(company_id=company_id, code=g["code"], name=g["name"],
                           version="1.0", description=g["description"],
                           status="active")
        db.add(graph)
        db.flush()
        for nd in g["nodes"]:
            db.add(LogicNode(graph_id=graph.id, company_id=company_id,
                             seq=nd["seq"], key=nd["key"],
                             title=nd["title"], kind=nd["kind"], tool=nd["tool"],
                             label=nd["label"], params_json=nd["params_json"],
                             depends_json=nd["depends_json"]))
        created.append(graph)
    if created:
        db.commit()
    return created


def get_active_plan(db: Session, company_id: int, agent_code: str = "") -> Optional[List[Dict[str, Any]]]:
    """按 Agent code 读 active 图，返回与 mainline.PLAN 同构的步骤列表（无图返回 None）。"""
    code = "inspection-anomaly" if agent_code == "inspection-analyst" else "sales-drop"
    seed_graphs(db, company_id)  # 首次调用幂等落库
    graph = db.query(LogicGraph).filter(
        LogicGraph.company_id == company_id,
        LogicGraph.code == code,
        LogicGraph.status == "active").first()
    if not graph:
        return None
    nodes = [n for n in graph.nodes if n.kind != ""]
    nodes.sort(key=lambda n: n.seq)
    plan: List[Dict[str, Any]] = []
    for n in nodes:
        try:
            params = json.loads(n.params_json or "{}")
        except (TypeError, ValueError):
            params = {}
        try:
            depends = json.loads(n.depends_json or "[]")
        except (TypeError, ValueError):
            depends = []
        step: Dict[str, Any] = {"seq": n.seq, "title": n.title, "kind": n.kind}
        if n.tool:
            step["tool"] = n.tool
        if depends:
            step["depends"] = depends
        if params:
            step["params"] = params
        plan.append(step)
    return plan


def list_graphs(db: Session, company_id: int) -> List[Dict[str, Any]]:
    seed_graphs(db, company_id)
    rows = db.query(LogicGraph).filter(LogicGraph.company_id == company_id)\
        .order_by(LogicGraph.id).all()
    return [{
        "id": g.id, "code": g.code, "name": g.name, "version": g.version,
        "description": g.description, "status": g.status,
        "node_count": len(g.nodes),
        "updated_at": g.updated_at.isoformat() if g.updated_at else "",
    } for g in rows]


def get_graph(db: Session, company_id: int, graph_id: int) -> Optional[Dict[str, Any]]:
    g = db.query(LogicGraph).filter(LogicGraph.id == graph_id,
                                    LogicGraph.company_id == company_id).first()
    if not g:
        return None
    nodes = sorted(g.nodes, key=lambda n: n.seq)
    return {
        "id": g.id, "code": g.code, "name": g.name, "version": g.version,
        "description": g.description, "status": g.status,
        "nodes": [{
            "id": n.id, "seq": n.seq, "key": n.key, "title": n.title,
            "kind": n.kind, "tool": n.tool, "label": n.label,
            "params": _safe_json(n.params_json, {}),
            "depends": _safe_json(n.depends_json, []),
        } for n in nodes],
    }


def update_node(db: Session, company_id: int, node_id: int, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """更新图节点（title/kind/tool/params/depends/label）。仅允许改本租户图内节点。"""
    n = db.query(LogicNode).join(LogicGraph, LogicGraph.id == LogicNode.graph_id).filter(
        LogicNode.id == node_id, LogicGraph.company_id == company_id).first()
    if not n:
        return None
    if "title" in patch and patch["title"] is not None:
        n.title = str(patch["title"])
    if "kind" in patch and patch["kind"] is not None:
        n.kind = str(patch["kind"])
    if "tool" in patch and patch["tool"] is not None:
        n.tool = str(patch["tool"])
    if "label" in patch and patch["label"] is not None:
        n.label = str(patch["label"])
    if "params" in patch:
        n.params_json = json.dumps(patch["params"] or {}, ensure_ascii=False)
    if "depends" in patch:
        n.depends_json = json.dumps(patch["depends"] or [], ensure_ascii=False)
    db.commit()
    return get_graph(db, company_id, n.graph_id)


def activate_graph(db: Session, company_id: int, graph_id: int) -> Optional[Dict[str, Any]]:
    """激活某图（同租户同 code 其他图置 draft）。"""
    g = db.query(LogicGraph).filter(LogicGraph.id == graph_id,
                                    LogicGraph.company_id == company_id).first()
    if not g:
        return None
    db.query(LogicGraph).filter(
        LogicGraph.company_id == company_id,
        LogicGraph.code == g.code).update({"status": "draft"})
    g.status = "active"
    db.commit()
    return get_graph(db, company_id, graph_id)


def _safe_json(raw: str, fallback: Any) -> Any:
    try:
        return json.loads(raw or "")
    except (TypeError, ValueError):
        return fallback
