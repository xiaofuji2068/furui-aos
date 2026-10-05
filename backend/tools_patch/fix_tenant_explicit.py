# -*- coding: utf-8 -*-
"""TASK-020 收口：ontology 持久化 + admin eval-contract + API 层显式传租户 company_id。

RLS 已启用（含 FORCE），写死 company_id=1 会在 PG 多租户下被 WITH CHECK 拦截
或写错租户。全部改为显式 company_id 参数（默认 1 兼容 SQLite 演示调用）。
"""
import io

ROOT = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app"

# ---------- 1) ontology/__init__.py ----------
p = ROOT + r"\ontology\__init__.py"
with io.open(p, "r", encoding="utf-8") as f:
    src = f.read()

# 1a. _upsert_db_object：加 company_id 参数 + 查询过滤
old = '''def _upsert_db_object(db, obj: OntologyObject) -> OntologyObjectRow:
    row = db.query(OntologyObjectRow).filter_by(type=obj.type, object_id=obj.id).first()
    props = json.dumps(obj.properties, ensure_ascii=False)
    if row:
        row.properties = props
    else:
        row = OntologyObjectRow(company_id=1, type=obj.type, object_id=obj.id, properties=props)
        db.add(row)
    _write_outbox(db, entity_type="object", op="upsert", obj_type=obj.type,
                  obj_id=obj.id, payload=obj.properties)
    return row'''
new = '''def _upsert_db_object(db, obj: OntologyObject, company_id: int = 1) -> OntologyObjectRow:
    row = db.query(OntologyObjectRow).filter_by(
        company_id=company_id, type=obj.type, object_id=obj.id).first()
    props = json.dumps(obj.properties, ensure_ascii=False)
    if row:
        row.properties = props
    else:
        row = OntologyObjectRow(company_id=company_id, type=obj.type,
                                object_id=obj.id, properties=props)
        db.add(row)
    _write_outbox(db, entity_type="object", op="upsert", obj_type=obj.type,
                  obj_id=obj.id, payload=obj.properties, company_id=company_id)
    return row'''
assert old in src, "1a anchor"
src = src.replace(old, new, 1)

# 1b. _upsert_db_link
old = '''def _upsert_db_link(db, link: OntologyLink) -> OntologyLinkRow:
    """按 (type, source_id, target_id) 幂等 upsert 一条关系。"""
    row = (db.query(OntologyLinkRow)
           .filter_by(type=link.type, source_id=link.source_id, target_id=link.target_id)
           .first())
    props = json.dumps(link.properties, ensure_ascii=False)
    if row:
        row.properties = props
    else:
        row = OntologyLinkRow(company_id=1, type=link.type, source_id=link.source_id,
                              target_id=link.target_id, properties=props)
        db.add(row)
    _write_outbox(db, entity_type="link", op="upsert", obj_type=link.type,
                  obj_id=link.source_id, payload={
                      "type": link.type, "source_id": link.source_id,
                      "target_id": link.target_id, "properties": link.properties,
                  })
    return row'''
new = '''def _upsert_db_link(db, link: OntologyLink, company_id: int = 1) -> OntologyLinkRow:
    """按 (type, source_id, target_id) 幂等 upsert 一条关系。"""
    row = (db.query(OntologyLinkRow)
           .filter_by(company_id=company_id, type=link.type,
                      source_id=link.source_id, target_id=link.target_id)
           .first())
    props = json.dumps(link.properties, ensure_ascii=False)
    if row:
        row.properties = props
    else:
        row = OntologyLinkRow(company_id=company_id, type=link.type,
                              source_id=link.source_id,
                              target_id=link.target_id, properties=props)
        db.add(row)
    _write_outbox(db, entity_type="link", op="upsert", obj_type=link.type,
                  obj_id=link.source_id, payload={
                      "type": link.type, "source_id": link.source_id,
                      "target_id": link.target_id, "properties": link.properties,
                  }, company_id=company_id)
    return row'''
assert old in src, "1b anchor"
src = src.replace(old, new, 1)

# 1c. _write_outbox
old = '''def _write_outbox(db, *, entity_type: str, op: str, obj_type: str,
                  obj_id: str, payload: Any) -> None:
    """Outbox 打点：与写入同事务追加一条待投影记录（图谱 20-04 Outbox）。"""
    db.add(OntologyOutboxRow(
        company_id=1, entity_type=entity_type, op=op,
        obj_type=obj_type, obj_id=obj_id,
        payload=json.dumps(payload, ensure_ascii=False, default=str),
        status="pending",
    ))'''
new = '''def _write_outbox(db, *, entity_type: str, op: str, obj_type: str,
                  obj_id: str, payload: Any, company_id: int = 1) -> None:
    """Outbox 打点：与写入同事务追加一条待投影记录（图谱 20-04 Outbox）。"""
    db.add(OntologyOutboxRow(
        company_id=company_id, entity_type=entity_type, op=op,
        obj_type=obj_type, obj_id=obj_id,
        payload=json.dumps(payload, ensure_ascii=False, default=str),
        status="pending",
    ))'''
assert old in src, "1c anchor"
src = src.replace(old, new, 1)

# 1d. project_outbox：按租户消费 + 快照按租户
old = '''def project_outbox(db, force: bool = False) -> Dict[str, Any]:'''
new = '''def project_outbox(db, force: bool = False, company_id: int = 1) -> Dict[str, Any]:'''
assert old in src, "1d anchor"
src = src.replace(old, new, 1)

old = '''    pending = db.query(OntologyOutboxRow).filter(
        OntologyOutboxRow.status == "pending").all()'''
new = '''    pending = db.query(OntologyOutboxRow).filter(
        OntologyOutboxRow.company_id == company_id,
        OntologyOutboxRow.status == "pending").all()'''
assert old in src, "1d2 anchor"
src = src.replace(old, new, 1)

old = '''    nodes = []
    seen = set()
    for r in db.query(OntologyObjectRow).order_by(OntologyObjectRow.id).all():
        key = f"{r.type}:{r.object_id}"
        if key not in seen:
            seen.add(key)
            nodes.append({"type": r.type, "id": r.object_id})
    edges = [{
        "type": r.type, "source": r.source_id, "target": r.target_id,
    } for r in db.query(OntologyLinkRow).order_by(OntologyLinkRow.id).all()]

    rev_row = db.query(OntologySchemaRevision).order_by(
        OntologySchemaRevision.id.desc()).first()
    revision = rev_row.revision if rev_row else ""

    snap = db.query(OntologyGraphSnapshot).filter_by(
        company_id=1, snapshot_key="graph-full").first()'''
new = '''    nodes = []
    seen = set()
    for r in db.query(OntologyObjectRow).filter(
            OntologyObjectRow.company_id == company_id
    ).order_by(OntologyObjectRow.id).all():
        key = f"{r.type}:{r.object_id}"
        if key not in seen:
            seen.add(key)
            nodes.append({"type": r.type, "id": r.object_id})
    edges = [{
        "type": r.type, "source": r.source_id, "target": r.target_id,
    } for r in db.query(OntologyLinkRow).filter(
        OntologyLinkRow.company_id == company_id
    ).order_by(OntologyLinkRow.id).all()]

    rev_row = db.query(OntologySchemaRevision).filter(
        OntologySchemaRevision.company_id == company_id
    ).order_by(OntologySchemaRevision.id.desc()).first()
    revision = rev_row.revision if rev_row else ""

    snap = db.query(OntologyGraphSnapshot).filter_by(
        company_id=company_id, snapshot_key="graph-full").first()'''
assert old in src, "1d3 anchor"
src = src.replace(old, new, 1)

old = '''        db.add(OntologyGraphSnapshot(
            company_id=1, snapshot_key="graph-full", payload=payload,
            node_count=len(nodes), link_count=len(edges), revision=revision,
        ))'''
new = '''        db.add(OntologyGraphSnapshot(
            company_id=company_id, snapshot_key="graph-full", payload=payload,
            node_count=len(nodes), link_count=len(edges), revision=revision,
        ))'''
assert old in src, "1d4 anchor"
src = src.replace(old, new, 1)

# 1e. get_graph_snapshot：按租户读
old = '''def get_graph_snapshot(db) -> Dict[str, Any]:
    """读取图快照；outbox 有未投影变更时先自动投影（保证 5s 内可见）。"""
    pending_before = db.query(OntologyOutboxRow).filter(
        OntologyOutboxRow.status == "pending").count()
    if pending_before:
        project_outbox(db)
    snap = db.query(OntologyGraphSnapshot).filter_by(
        company_id=1, snapshot_key="graph-full").order_by(
        OntologyGraphSnapshot.id.desc()).first()
    if not snap:
        project_outbox(db)
        snap = db.query(OntologyGraphSnapshot).filter_by(
            company_id=1, snapshot_key="graph-full").order_by(
            OntologyGraphSnapshot.id.desc()).first()
    pending_now = db.query(OntologyOutboxRow).filter(
        OntologyOutboxRow.status == "pending").count()'''
new = '''def get_graph_snapshot(db, company_id: int = 1) -> Dict[str, Any]:
    """读取图快照；outbox 有未投影变更时先自动投影（保证 5s 内可见）。"""
    pending_before = db.query(OntologyOutboxRow).filter(
        OntologyOutboxRow.company_id == company_id,
        OntologyOutboxRow.status == "pending").count()
    if pending_before:
        project_outbox(db, company_id=company_id)
    snap = db.query(OntologyGraphSnapshot).filter_by(
        company_id=company_id, snapshot_key="graph-full").order_by(
        OntologyGraphSnapshot.id.desc()).first()
    if not snap:
        project_outbox(db, company_id=company_id)
        snap = db.query(OntologyGraphSnapshot).filter_by(
            company_id=company_id, snapshot_key="graph-full").order_by(
            OntologyGraphSnapshot.id.desc()).first()
    pending_now = db.query(OntologyOutboxRow).filter(
        OntologyOutboxRow.company_id == company_id,
        OntologyOutboxRow.status == "pending").count()'''
assert old in src, "1e anchor"
src = src.replace(old, new, 1)

# 1f. seed_ontology：按租户种子
old = '''def seed_ontology(db) -> None:
    """把内存 demo 本体幂等写入数据库（Phase 1 持久化种子）。

    可重复调用：同一 (type, object_id) 不会重复插入；
    Link 关系同样按 (type, source_id, target_id) 幂等。
    """
    for t in ONTO["types"].values():
        for obj in t._store.values():
            _upsert_db_object(db, obj)
    for link in ONTO.get("links", []):
        _upsert_db_link(db, link)
    if not db.query(OntologySchemaRevision).first():
        db.add(OntologySchemaRevision(company_id=1, revision="r1",
                                      note="demo seed (Phase 1 持久化)"))
    db.commit()'''
new = '''def seed_ontology(db, company_id: int = 1) -> None:
    """把内存 demo 本体幂等写入数据库（Phase 1 持久化种子）。

    可重复调用：同一 (type, object_id) 不会重复插入；
    Link 关系同样按 (type, source_id, target_id) 幂等。
    """
    for t in ONTO["types"].values():
        for obj in t._store.values():
            _upsert_db_object(db, obj, company_id=company_id)
    for link in ONTO.get("links", []):
        _upsert_db_link(db, link, company_id=company_id)
    if not db.query(OntologySchemaRevision).filter(
            OntologySchemaRevision.company_id == company_id).first():
        db.add(OntologySchemaRevision(company_id=company_id, revision="r1",
                                      note="demo seed (Phase 1 持久化)"))
    db.commit()'''
assert old in src, "1f anchor"
src = src.replace(old, new, 1)

with io.open(p, "w", encoding="utf-8") as f:
    f.write(src)
print("OK: ontology/__init__.py")

# ---------- 2) api/ontology_api.py ----------
p2 = ROOT + r"\api\ontology_api.py"
with io.open(p2, "r", encoding="utf-8") as f:
    src2 = f.read()

old = '    return get_graph_snapshot(db)'
new = '    return get_graph_snapshot(db, company_id=user.company_id or 1)'
assert old in src2, "2a anchor"
src2 = src2.replace(old, new, 1)

old = '    r = project_outbox(db)'
new = '    r = project_outbox(db, company_id=user.company_id or 1)'
assert old in src2, "2b anchor"
src2 = src2.replace(old, new, 1)

with io.open(p2, "w", encoding="utf-8") as f:
    f.write(src2)
print("OK: api/ontology_api.py")

# ---------- 3) api/admin.py eval-contracts ----------
p3 = ROOT + r"\api\admin.py"
with io.open(p3, "r", encoding="utf-8") as f:
    src3 = f.read()

old = '''            row = EvalContract(company_id=1, name=req.name, description=req.description,
                               metric=req.metric, operator=req.operator,
                               threshold=req.threshold, enabled=req.enabled)'''
new = '''            row = EvalContract(company_id=_auth.company_id or 1, name=req.name,
                               description=req.description,
                               metric=req.metric, operator=req.operator,
                               threshold=req.threshold, enabled=req.enabled)'''
assert old in src3, "3 anchor"
src3 = src3.replace(old, new, 1)

with io.open(p3, "w", encoding="utf-8") as f:
    f.write(src3)
print("OK: api/admin.py")
