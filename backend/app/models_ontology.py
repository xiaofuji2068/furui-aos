"""本体持久化模型（Phase 1 P0，对应图谱 20-01 / 20-02 / 20-04）。

把 ontology/__init__.py 的内存语义对象落到数据库，解决"重启即丢、无法承载真实企业数据"的硬伤。

设计要点：
- Object / Link / Function 三类语义对象持久化；Function 的逻辑（handler）仍驻留代码，
  这里只存"类型注册"与"对象实例/关系"数据，符合图谱"元模型 + 权威对象"的分工。
- properties 用 JSON 文本列存储（SQLite 无原生 JSON 类型），读取时反序列化为 dict。
- 唯一约束 (type, object_id) 保证种子幂等 upsert。
- SchemaRevision 记录本体版本演进（图谱 20-02 要求），Phase 1 仅打基线 r1。
"""
from __future__ import annotations

import json
import re
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped

from .db import Base


class OntologyType(Base):
    """Object Type 注册（图谱 20-02 元模型）。"""

    __tablename__ = "ontology_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False, comment="如 Order / Device")
    description = Column(String(255), default="")
    primary_key_field = Column(String(32), default="id")
    created_at = Column(DateTime, default=datetime.utcnow)


class OntologyObjectRow(Base):
    """语义对象实例（图谱 20-01 的 Object）。"""

    __tablename__ = "ontology_objects"
    __table_args__ = (
        UniqueConstraint("type", "object_id", name="uq_onto_obj"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, default=1, index=True,
                        comment="租户键（图谱 60-02）；默认 1=单租户 MVP")
    type = Column(String(64), nullable=False, index=True, comment="对象类型")
    object_id = Column(String(128), nullable=False, comment="语义 id（如 ORD-2026-0817）")
    properties = Column(Text, default="{}", comment="JSON 序列化属性")
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_properties(self) -> dict:
        try:
            return json.loads(self.properties or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}


class OntologyLinkRow(Base):
    """实体间关系（图谱 20-01 的 Link）。"""

    __tablename__ = "ontology_links"
    __table_args__ = (
        UniqueConstraint("type", "source_id", "target_id", name="uq_onto_link"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, default=1, index=True,
                        comment="租户键（图谱 60-02）；默认 1=单租户 MVP")
    type = Column(String(64), nullable=False, index=True, comment="关系类型")
    source_id = Column(String(128), nullable=False, comment="源对象 id")
    target_id = Column(String(128), nullable=False, comment="目标对象 id")
    properties = Column(Text, default="{}", comment="JSON 序列化属性")

    def to_properties(self) -> dict:
        try:
            return json.loads(self.properties or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}


class OntologySchemaRevision(Base):
    """本体 Schema 版本（图谱 20-02 Schema Revision）。"""

    __tablename__ = "ontology_schema_revisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, default=1, index=True,
                        comment="租户键（图谱 60-02）；默认 1=单租户 MVP")
    revision = Column(String(32), nullable=False, comment="版本号，如 r1")
    note = Column(String(255), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


def bump_revision(db, note: str = "", company_id: int = 1) -> str:
    """打一个递增的新 Schema Revision（图谱 20-02 演进机制）。

    解析现有最大 r{n} 编号并 +1，写入新行后返回新版本号。
    可重复调用；版本号不会重复。
    """
    max_n = 0
    for r in db.query(OntologySchemaRevision).all():
        m = re.match(r"^r(\d+)$", r.revision or "")
        if m:
            max_n = max(max_n, int(m.group(1)))
    new_rev = f"r{max_n + 1}"
    db.add(OntologySchemaRevision(company_id=company_id, revision=new_rev, note=note))
    db.commit()
    return new_rev


class OntologyOutboxRow(Base):
    """本体写入 Outbox（图谱 20-04 权威写链 / Outbox）。

    每次 Object/Link 写入（upsert）都同步追加一条记录（与写入同事务），
    由 Projector 消费并投影到 GraphSnapshot —— 保证"写多少，投影多少"，
    即使投影失败，outbox 也完整保留，可重放。
    """

    __tablename__ = "ontology_outbox"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, default=1, index=True)
    entity_type = Column(String(16), nullable=False, comment="object / link")
    op = Column(String(16), nullable=False, default="upsert", comment="upsert / delete")
    obj_type = Column(String(64), default="", comment="对象类型或 Link 类型")
    obj_id = Column(String(128), default="", comment="对象 id 或 source_id")
    payload = Column(Text, default="{}", comment="变更对象 JSON 快照（供审计/回放）")
    status = Column(String(16), nullable=False, default="pending", index=True,
                    comment="pending / processed")
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)


class OntologyGraphSnapshot(Base):
    """本体图快照（图谱 20-04 Projector / GraphSnapshot）。

    投影结果：全量节点 + 关系（JSON 字段存储，最小可用版），
    由 Projector 从当前 Object/Link 表重建，覆盖 outbox 全部 pending 事件。
    """

    __tablename__ = "ontology_graph_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, default=1, index=True)
    snapshot_key = Column(String(64), nullable=False, default="graph-full", index=True)
    payload = Column(Text, default="{}", comment="JSON: {nodes, edges}")
    node_count = Column(Integer, default=0)
    link_count = Column(Integer, default=0)
    revision = Column(String(32), default="", comment="投影时本体 Schema 版本")
    created_at = Column(DateTime, default=datetime.utcnow)
