"""Palantir Ontology 风格的语义数据层。

核心理念：**AI 不直接查 SQL 表，而是操作语义对象（Object）+ 关系（Link）+ 动作（Function）**。

三类对象：
- Object: 企业实体（订单、客户、设备、员工、产品…）
- Link:   实体之间的关系（订单-客户、设备-位置、知识库-文档…）
- Function: 在语义层可调用的动作（创建工单、发起审批、推送通知…）

为简化演示，这里使用内存版 + Mock 数据；真实部署可对接 Foundry-style 的数据集/数据连接器。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from app.db import SessionLocal
from app.models_ontology import (
    OntologyGraphSnapshot,
    OntologyLinkRow,
    OntologyObjectRow,
    OntologyOutboxRow,
    OntologySchemaRevision,
)


# ---------- Object（实体） ----------

@dataclass
class OntologyObject:
    """一个语义实体，类似 Palantir 的 Object Type 实例。"""
    type: str               # e.g. "Order" / "Customer" / "Device"
    id: str                 # e.g. "ORD-2026-0817"
    properties: Dict[str, Any] = field(default_factory=dict)


class ObjectType:
    """Object 类型注册。"""

    def __init__(self, name: str, description: str, primary_key: str = "id"):
        self.name = name
        self.description = description
        self.primary_key = primary_key
        self._store: Dict[str, OntologyObject] = {}

    def upsert(self, obj: OntologyObject) -> OntologyObject:
        if obj.type != self.name:
            raise ValueError(f"Object type mismatch: expect {self.name}, got {obj.type}")
        key = str(obj.properties.get(self.primary_key) or obj.id)
        obj.id = key
        self._store[key] = obj
        return obj

    def get(self, key: str) -> Optional[OntologyObject]:
        return self._store.get(key)

    def list(self, limit: int = 100) -> List[OntologyObject]:
        return list(self._store.values())[:limit]

    def search(self, predicate: Callable[[OntologyObject], bool], limit: int = 50) -> List[OntologyObject]:
        return [o for o in self._store.values() if predicate(o)][:limit]


# ---------- Link（关系） ----------

@dataclass
class OntologyLink:
    """实体间关系，类似 Palantir 的 Link Type。"""
    type: str               # e.g. "OrderToCustomer"
    source_id: str
    target_id: str
    properties: Dict[str, Any] = field(default_factory=dict)


# ---------- Function（语义动作） ----------

@dataclass
class OntologyFunction:
    """AI 可调用的语义动作（computer_use 风格的工具）。"""
    name: str
    description: str
    parameters: Dict[str, Any]   # JSON Schema
    handler: Callable[..., Any]


# ---------- 全局本体（演示版） ----------

def build_demo_ontology() -> Dict[str, Any]:
    """构造一个完整的演示用 Ontology。"""

    # 1. 实体类型
    customer_t = ObjectType("Customer", "客户主数据")
    order_t = ObjectType("Order", "销售订单")
    device_t = ObjectType("Device", "设备")
    product_t = ObjectType("Product", "产品")
    workorder_t = ObjectType("WorkOrder", "工单")
    ticket_t = ObjectType("Ticket", "事件 / 风险")
    # 核电巡检实体（TASK-002：监测站/设备 + 厂房区域 + 指标 + 巡检记录）
    station_t = ObjectType("MonitoringStation", "辐射监测站")
    area_t = ObjectType("Area", "厂房区域")
    metric_t = ObjectType("MetricRecord", "设备指标读数")
    inspection_t = ObjectType("InspectionRecord", "巡检记录")

    # 2. 演示数据 — 傅瑞科技业务语境（工业空间智能 · 核电等高危场景）
    #    与 data_gateway.py 的 ERP/CRM 样例（恒力重工 / 中广核工程 / 浙能集团 三大战略客户）
    #    保持一致；对象 id 与链接关系为稳定标识，供测试与前端复用。
    customers = [
        ("CUS-001", "恒力重工",     {"name": "恒力重工",   "industry": "装备制造", "region": "华东", "tier": "A"}),
        ("CUS-002", "中广核工程",   {"name": "中广核工程", "industry": "核电",     "region": "华南", "tier": "A"}),
        ("CUS-003", "浙能集团",     {"name": "浙能集团",   "industry": "能源",     "region": "华东", "tier": "A"}),
    ]
    for cid, name, props in customers:
        customer_t.upsert(OntologyObject(type="Customer", id=cid, properties={"id": cid, **props}))

    products = [
        ("SKU-A12", "辐射监测数字孪生平台", {"name": "辐射监测数字孪生平台", "category": "软件", "stock": 12, "price": 480000}),
        ("SKU-B07", "VR 安全培训系统",     {"name": "VR 安全培训系统",     "category": "软件", "stock": 30, "price": 260000}),
        ("SKU-C33", "三维建模服务",        {"name": "三维建模服务",        "category": "服务", "stock": 99, "price": 86000}),
    ]
    for sid, name, props in products:
        product_t.upsert(OntologyObject(type="Product", id=sid, properties={"id": sid, **props}))

    orders = [
        ("ORD-2026-0817", "CUS-001", "SKU-A12", {"qty": 1, "amount": 480000, "region": "华东", "status": "已下推"}),
        ("ORD-2026-0818", "CUS-002", "SKU-B07", {"qty": 2, "amount": 520000, "region": "华南", "status": "待发货"}),
        ("ORD-2026-0819", "CUS-001", "SKU-A12", {"qty": 1, "amount": 480000, "region": "华东", "status": "已下推"}),
        ("ORD-2026-0820", "CUS-003", "SKU-C33", {"qty": 5, "amount": 430000, "region": "华东", "status": "已完成"}),
        ("ORD-2026-0821", "CUS-002", "SKU-A12", {"qty": 1, "amount": 480000, "region": "华南", "status": "已完成"}),
    ]
    for oid, cus, sku, props in orders:
        order_t.upsert(OntologyObject(type="Order", id=oid, properties={"id": oid, "customer_id": cus, "sku": sku, **props}))

    # 在役设备（客户现场，关联产品 SKU）
    devices = [
        ("DEV-SKU-A12", "辐射监测站·现场在线", {"linked_sku": "SKU-A12", "status": "online", "site": "华东核电厂区"}),
        ("DEV-SKU-B07", "核岛巡检无人机",     {"linked_sku": "SKU-B07", "status": "online", "site": "华南核电基地"}),
        ("DEV-SKU-C33", "三维激光扫描仪",     {"linked_sku": "SKU-C33", "status": "maintenance", "site": "项目现场"}),
    ]
    for did, name, props in devices:
        device_t.upsert(OntologyObject(type="Device", id=did, properties={"id": did, "name": name, **props}))

    # 工单（现场运维 / 数据任务）
    workorders = [
        ("WO-001", "辐射监测站告警排查", {"title": "辐射监测站告警排查", "priority": "high", "status": "in_progress"}),
        ("WO-002", "点云数据处理任务",   {"title": "点云数据处理任务",   "priority": "medium", "status": "pending"}),
    ]
    for wid, _, props in workorders:
        workorder_t.upsert(OntologyObject(type="WorkOrder", id=wid, properties={"id": wid, **props}))

    # 风险事件
    ticket_t.upsert(OntologyObject(type="Ticket", id="T-001", properties={
        "id": "T-001", "title": "华东区域本周订单下降 18%", "severity": "high", "category": "销售异常"
    }))
    ticket_t.upsert(OntologyObject(type="Ticket", id="T-002", properties={
        "id": "T-002", "title": "三维建模交付数据质量告警", "severity": "medium", "category": "质量风险"
    }))

    # 核电厂房区域（核岛 / 常规岛 / 辅助厂房）
    areas = [
        ("AREA-NI", "核岛",   {"name": "核岛",   "zone": "A", "risk_level": "高"}),
        ("AREA-CI", "常规岛", {"name": "常规岛", "zone": "B", "risk_level": "中"}),
        ("AREA-AB", "辅助厂房", {"name": "辅助厂房", "zone": "C", "risk_level": "中"}),
    ]
    for aid, _, props in areas:
        area_t.upsert(OntologyObject(type="Area", id=aid, properties={"id": aid, **props}))

    # 监测站（含主冷却泵/蒸汽发生器/稳压器/管道阀门监测点，与 data_gateway 巡检样例一致）
    stations = [
        ("MS-01", "1号辐射监测站",   "AREA-NI", {"name": "1号辐射监测站",   "device": "辐射剂量率探头",  "status": "alarm"}),
        ("MS-02", "主冷却泵在线监测", "AREA-CI", {"name": "主冷却泵在线监测", "device": "主冷却泵",        "status": "alarm"}),
        ("MS-03", "蒸汽发生器监测点", "AREA-NI", {"name": "蒸汽发生器监测点", "device": "蒸汽发生器",      "status": "normal"}),
        ("MS-04", "空压机在线监测",   "AREA-AB", {"name": "空压机在线监测",   "device": "空压机",          "status": "alarm"}),
        ("MS-05", "稳压器监测点",     "AREA-NI", {"name": "稳压器监测点",     "device": "稳压器",          "status": "normal"}),
    ]
    for sid, _, area, props in stations:
        station_t.upsert(OntologyObject(type="MonitoringStation", id=sid, properties={"id": sid, "area_id": area, **props}))

    # 设备（现场监测硬件，关联 SKU 与监测站）
    devices = devices + [
        ("DEV-MS-01", "辐射监测站现场终端", {"linked_sku": "SKU-A12", "status": "online", "site": "核岛", "station_code": "MS-01"}),
        ("DEV-MS-02", "主冷却泵温振传感器", {"linked_sku": "SKU-A12", "status": "online", "site": "常规岛", "station_code": "MS-02"}),
        ("DEV-MS-03", "蒸汽发生器监测终端", {"linked_sku": "SKU-A12", "status": "online", "site": "核岛", "station_code": "MS-03"}),
        ("DEV-MS-04", "空压机振动传感器",   {"linked_sku": "SKU-A12", "status": "online", "site": "辅助厂房", "station_code": "MS-04"}),
        ("DEV-MS-05", "稳压器监测终端",     {"linked_sku": "SKU-A12", "status": "online", "site": "核岛", "station_code": "MS-05"}),
    ]
    for did, name, props in devices:
        device_t.upsert(OntologyObject(type="Device", id=did, properties={"id": did, "name": name, **props}))

    # 设备指标读数（8 月告警 3 站 + 正常 2 站；与 erp_crm.db device_metrics 一致）
    metrics = [
        ("MET-001", "MS-01", "radiation", 26.8, "uSv/h", 20.0, "alarm"),
        ("MET-002", "MS-02", "temperature", 92.4, "℃", 85.0, "alarm"),
        ("MET-003", "MS-03", "radiation", 8.6, "uSv/h", 20.0, "normal"),
        ("MET-004", "MS-04", "vibration", 7.2, "mm/s", 6.0, "alarm"),
        ("MET-005", "MS-05", "radiation", 6.3, "uSv/h", 20.0, "normal"),
    ]
    for mid, station, mtype, val, unit, thr, status in metrics:
        metric_t.upsert(OntologyObject(type="MetricRecord", id=mid, properties={
            "id": mid, "station_code": station, "metric": mtype, "value": val,
            "unit": unit, "threshold": thr, "status": status, "month": "2026-08",
        }))

    # 巡检记录（3 条异常 + 2 条正常）
    inspections = [
        ("INSP-001", "MS-01", "2026-08-15", "辐射剂量率 26.8uSv/h 超限，已派员复测"),
        ("INSP-002", "MS-02", "2026-08-15", "主冷却泵温度 92.4℃ 超限，检查冷却回路"),
        ("INSP-003", "MS-04", "2026-08-15", "空压机振动 7.2mm/s 超限，计划停机检修"),
        ("INSP-004", "MS-03", "2026-08-16", "蒸汽发生器监测正常，无异常"),
        ("INSP-005", "MS-05", "2026-08-16", "稳压器监测正常，无异常"),
    ]
    for iid, station, date, note in inspections:
        inspection_t.upsert(OntologyObject(type="InspectionRecord", id=iid, properties={
            "id": iid, "station_code": station, "inspect_date": date, "note": note,
        }))

    # 巡检工单（与审批通过后落库的工单一致）
    workorder_t.upsert(OntologyObject(type="WorkOrder", id="WO-003", properties={
        "id": "WO-003", "title": "1号辐射监测站巡检异常处置", "priority": "high",
        "status": "待处置", "station_code": "MS-01",
    }))

    # 3. Link（实体间关系）— Order→Customer、Device→Product、WorkOrder→Device、Ticket→WorkOrder
    links = [
        OntologyLink(type="OrderToCustomer", source_id="ORD-2026-0817", target_id="CUS-001"),
        OntologyLink(type="OrderToCustomer", source_id="ORD-2026-0818", target_id="CUS-002"),
        OntologyLink(type="OrderToCustomer", source_id="ORD-2026-0819", target_id="CUS-001"),
        OntologyLink(type="OrderToCustomer", source_id="ORD-2026-0820", target_id="CUS-003"),
        OntologyLink(type="OrderToCustomer", source_id="ORD-2026-0821", target_id="CUS-002"),
        OntologyLink(type="DeviceToProduct", source_id="DEV-SKU-A12", target_id="SKU-A12"),
        OntologyLink(type="DeviceToProduct", source_id="DEV-SKU-B07", target_id="SKU-B07"),
        OntologyLink(type="DeviceToProduct", source_id="DEV-SKU-C33", target_id="SKU-C33"),
        OntologyLink(type="WorkOrderToDevice", source_id="WO-001", target_id="DEV-SKU-C33"),
        OntologyLink(type="WorkOrderToDevice", source_id="WO-002", target_id="DEV-SKU-A12"),
        OntologyLink(type="TicketToWorkOrder", source_id="T-002", target_id="WO-002"),
        # 核电巡检关联（TASK-002）
        OntologyLink(type="StationToArea", source_id="MS-01", target_id="AREA-NI"),
        OntologyLink(type="StationToArea", source_id="MS-02", target_id="AREA-CI"),
        OntologyLink(type="StationToArea", source_id="MS-03", target_id="AREA-NI"),
        OntologyLink(type="StationToArea", source_id="MS-04", target_id="AREA-AB"),
        OntologyLink(type="StationToArea", source_id="MS-05", target_id="AREA-NI"),
        OntologyLink(type="MetricToStation", source_id="MET-001", target_id="MS-01"),
        OntologyLink(type="MetricToStation", source_id="MET-002", target_id="MS-02"),
        OntologyLink(type="MetricToStation", source_id="MET-003", target_id="MS-03"),
        OntologyLink(type="MetricToStation", source_id="MET-004", target_id="MS-04"),
        OntologyLink(type="MetricToStation", source_id="MET-005", target_id="MS-05"),
        OntologyLink(type="InspectionToStation", source_id="INSP-001", target_id="MS-01"),
        OntologyLink(type="InspectionToStation", source_id="INSP-002", target_id="MS-02"),
        OntologyLink(type="InspectionToStation", source_id="INSP-003", target_id="MS-04"),
        OntologyLink(type="InspectionToStation", source_id="INSP-004", target_id="MS-03"),
        OntologyLink(type="InspectionToStation", source_id="INSP-005", target_id="MS-05"),
        OntologyLink(type="WorkOrderToStation", source_id="WO-003", target_id="MS-01"),
        OntologyLink(type="DeviceToStation", source_id="DEV-MS-01", target_id="MS-01"),
        OntologyLink(type="DeviceToStation", source_id="DEV-MS-02", target_id="MS-02"),
        OntologyLink(type="DeviceToStation", source_id="DEV-MS-03", target_id="MS-03"),
        OntologyLink(type="DeviceToStation", source_id="DEV-MS-04", target_id="MS-04"),
        OntologyLink(type="DeviceToStation", source_id="DEV-MS-05", target_id="MS-05"),
    ]

    # 4. Function（语义动作）— Skills 调用的底层（handler 在模块级定义，见下方）

    functions = [
        OntologyFunction(
            name="create_workorder",
            description="在工单系统里创建一条新的设备工单",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "工单标题"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"], "default": "medium"},
                },
                "required": ["title"],
            },
            handler=_fn_create_workorder,
        ),
        OntologyFunction(
            name="send_notification",
            description="通过企微/钉钉/邮件向指定渠道推送一条通知",
            parameters={
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "通知渠道，如 'wechat' / 'dingtalk' / 'email'"},
                    "message": {"type": "string", "description": "通知正文"},
                },
                "required": ["channel", "message"],
            },
            handler=_fn_send_notification,
        ),
        OntologyFunction(
            name="analyze_inspection_anomaly",
            description="对核电监测站 8 月设备指标做异常归因：对比 7 月基线，输出告警站点、超限指标与环比结论",
            parameters={
                "type": "object",
                "properties": {
                    "month": {"type": "string", "description": "归因月份，如 2026-08"},
                },
                "required": ["month"],
            },
            handler=_fn_analyze_inspection,
        ),
        OntologyFunction(
            name="draft_report",
            description="草拟一份主题报告（销售/财务/运维等）",
            parameters={
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "audience": {"type": "string", "default": "管理层"},
                },
                "required": ["topic"],
            },
            handler=_fn_draft_report,
        ),
    ]

    return {
        "types": {
            "Customer": customer_t, "Order": order_t, "Device": device_t,
            "Product": product_t, "WorkOrder": workorder_t, "Ticket": ticket_t,
            "MonitoringStation": station_t, "Area": area_t,
            "MetricRecord": metric_t, "InspectionRecord": inspection_t,
        },
        "links": links,
        "functions": functions,
    }


# ---------- Function 处理器（模块级，可直接写库） ----------

def _fn_analyze_inspection(month: str = "2026-08") -> Dict[str, Any]:
    """巡检异常归因（演示）：基于本体内存数据做规则化归因，数字与样例库一致。"""
    stations = ONTO["types"]["MonitoringStation"].list()
    alarms = [s for s in stations if s.properties.get("status") == "alarm"]
    metrics = ONTO["types"]["MetricRecord"].list()
    detail = [
        {"station": m.properties.get("station_code"), "metric": m.properties.get("metric"),
         "value": m.properties.get("value"), "unit": m.properties.get("unit"),
         "threshold": m.properties.get("threshold"), "status": m.properties.get("status")}
        for m in metrics if m.properties.get("month") == month and m.properties.get("status") == "alarm"
    ]
    return {
        "month": month,
        "alarm_stations": len(alarms),
        "total_stations": len(stations),
        "previous_month_alarms": 0,
        "conclusion": f"{month} 共 {len(alarms)} 个监测站告警（上月 0 个），环比恶化",
        "top_alarms": detail,
    }


def _fn_create_workorder(title: str, priority: str = "medium") -> Dict[str, Any]:
    """创建工单：同时写库（持久化）与更新内存注册表（兜底）。"""
    db = SessionLocal()
    try:
        n = db.query(OntologyObjectRow).filter_by(type="WorkOrder").count()
        wid = f"WO-{n + 1:03d}"
        obj = OntologyObject(type="WorkOrder", id=wid, properties={
            "id": wid, "title": title, "priority": priority, "status": "pending"
        })
        _upsert_db_object(db, obj)
        db.commit()
        ONTO["types"]["WorkOrder"].upsert(obj)  # 兜底路径同步
        return {"created": wid, "title": title}
    finally:
        db.close()


def _fn_send_notification(channel: str, message: str) -> Dict[str, Any]:
    # 真实环境会接入企微/钉钉/Slack，这里直接模拟
    return {"channel": channel, "message": message, "delivered": True}


def _fn_draft_report(topic: str, audience: str = "管理层") -> Dict[str, Any]:
    return {"topic": topic, "audience": audience, "drafted": True}


# ---------- 持久化 ----------

def _row_to_object(row: OntologyObjectRow) -> OntologyObject:
    return OntologyObject(type=row.type, id=row.object_id, properties=row.to_properties())


def _upsert_db_object(db, obj: OntologyObject, company_id: int = 1) -> OntologyObjectRow:
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
    return row


def _upsert_db_link(db, link: OntologyLink, company_id: int = 1) -> OntologyLinkRow:
    """按 (type, source_id, target_id) 幂等 upsert 一条关系。"""
    db.flush()  # autoflush=False：先落 pending 再查，保证同事务内幂等（PG 唯一键）
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
    return row


def _write_outbox(db, *, entity_type: str, op: str, obj_type: str,
                  obj_id: str, payload: Any, company_id: int = 1) -> None:
    """Outbox 打点：与写入同事务追加一条待投影记录（图谱 20-04 Outbox）。"""
    db.add(OntologyOutboxRow(
        company_id=company_id, entity_type=entity_type, op=op,
        obj_type=obj_type, obj_id=obj_id,
        payload=json.dumps(payload, ensure_ascii=False, default=str),
        status="pending",
    ))


def project_outbox(db, force: bool = False, company_id: int = 1) -> Dict[str, Any]:
    """单线程 Projector：消费全部 pending Outbox，重建全量图快照（最小可用）。

    幂等：重复调用不产生副作用（已 processed 的跳过；快照整体重建覆盖）。
    force=True 时即使无 pending 也强制重建（供数据清理等场景使用）。
    返回本次投影统计；无 pending 且非 force 时返回 {"projected": 0, ...}。
    """
    pending = db.query(OntologyOutboxRow).filter(
        OntologyOutboxRow.company_id == company_id,
        OntologyOutboxRow.status == "pending").all()
    projected = len(pending)
    if not projected and not force:
        return {"projected": 0, "node_count": 0, "link_count": 0, "skipped": True}

    # 从当前权威表重建全量图（不依赖 outbox 内容，保证快照=当前状态）
    nodes = []
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
        company_id=company_id, snapshot_key="graph-full").first()
    payload = json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False)
    if snap:
        snap.payload = payload
        snap.node_count = len(nodes)
        snap.link_count = len(edges)
        snap.revision = revision
        snap.created_at = datetime.utcnow()
    else:
        db.add(OntologyGraphSnapshot(
            company_id=company_id, snapshot_key="graph-full", payload=payload,
            node_count=len(nodes), link_count=len(edges), revision=revision,
        ))

    now = datetime.utcnow()
    for row in pending:
        row.status = "processed"
        row.processed_at = now
    db.commit()
    return {"projected": projected, "node_count": len(nodes), "link_count": len(edges),
            "revision": revision}


def get_graph_snapshot(db, company_id: int = 1) -> Dict[str, Any]:
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
        OntologyOutboxRow.status == "pending").count()
    if not snap:
        return {"nodes": [], "edges": [], "node_count": 0, "link_count": 0,
                "revision": "", "pending": pending_now, "projected_at": None}
    try:
        data = json.loads(snap.payload or "{}")
    except (json.JSONDecodeError, TypeError):
        data = {}
    return {
        "nodes": data.get("nodes", []),
        "edges": data.get("edges", []),
        "node_count": snap.node_count,
        "link_count": snap.link_count,
        "revision": snap.revision,
        "pending": pending_now,
        "projected_at": snap.created_at.isoformat() if snap.created_at else None,
    }


def seed_ontology(db, company_id: int = 1) -> None:
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
    db.commit()


ONTO = build_demo_ontology()


def list_objects(type_name: str, limit: int = 50) -> List[OntologyObject]:
    """优先读数据库（持久化、重启不丢）；数据库不可用时回退到内存注册表。"""
    try:
        db = SessionLocal()
        try:
            rows = (
                db.query(OntologyObjectRow)
                .filter_by(type=type_name)
                .order_by(OntologyObjectRow.object_id)
                .limit(limit)
                .all()
            )
            if rows:
                return [_row_to_object(r) for r in rows]
        finally:
            db.close()
    except Exception:
        # 表尚未创建 / 连接异常：退回内存注册表，保证演示可用
        pass
    t = ONTO["types"].get(type_name)
    return t.list(limit=limit) if t else []


def list_links(type_name: str | None = None,
               source_id: str | None = None,
               target_id: str | None = None,
               limit: int = 200) -> List[Dict[str, Any]]:
    """查询关系（图谱 20-04 图探索的基础）。DB 优先，空表回退内存。

    返回统一结构：[{"type", "source_id", "target_id", "properties"}]
    """
    try:
        db = SessionLocal()
        try:
            q = db.query(OntologyLinkRow)
            if type_name:
                q = q.filter(OntologyLinkRow.type == type_name)
            if source_id:
                q = q.filter(OntologyLinkRow.source_id == source_id)
            if target_id:
                q = q.filter(OntologyLinkRow.target_id == target_id)
            rows = q.order_by(OntologyLinkRow.id).limit(limit).all()
            if rows:
                return [{
                    "type": r.type, "source_id": r.source_id,
                    "target_id": r.target_id, "properties": r.to_properties(),
                } for r in rows]
        finally:
            db.close()
    except Exception:
        # 表尚未创建 / 连接异常：退回内存链接表，保证演示可用
        pass
    out = []
    for link in ONTO.get("links", []):
        if type_name and link.type != type_name:
            continue
        if source_id and link.source_id != source_id:
            continue
        if target_id and link.target_id != target_id:
            continue
        out.append({
            "type": link.type, "source_id": link.source_id,
            "target_id": link.target_id, "properties": link.properties,
        })
        if len(out) >= limit:
            break
    return out


def _object_type(object_id: str) -> str:
    """根据对象 id 反查类型（DB 优先，内存兜底）。"""
    try:
        db = SessionLocal()
        try:
            row = db.query(OntologyObjectRow).filter_by(object_id=object_id).first()
            if row:
                return row.type
        finally:
            db.close()
    except Exception:
        pass
    for t in ONTO["types"].values():
        if t.get(object_id):
            return t.name
    return ""


def get_related(type_name: str, object_id: str, depth: int = 1) -> Dict[str, Any]:
    """沿 Link 双向遍历到指定深度（图谱 20-04 图探索）。

    返回 {root, nodes, edges}；edges 按 (type, source, target) 去重，
    direction 表示相对根对象的出入方向（in/out）。
    """
    seen_nodes: set = set()
    seen_edges: set = set()
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    queue = [(type_name, object_id, 0)]
    while queue:
        t, oid, d = queue.pop(0)
        key = f"{t}:{oid}"
        if key in seen_nodes or d > depth:
            continue
        seen_nodes.add(key)
        nodes.append({"type": t, "id": oid})
        for link in list_links():
            if link["source_id"] == oid:
                other, direction = link["target_id"], "out"
            elif link["target_id"] == oid:
                other, direction = link["source_id"], "in"
            else:
                continue
            nt = _object_type(other)
            if nt and d + 1 <= depth:
                ekey = (link["type"], link["source_id"], link["target_id"])
                if ekey not in seen_edges:
                    seen_edges.add(ekey)
                    edges.append({
                        "type": link["type"],
                        "source": link["source_id"],
                        "target": link["target_id"],
                        "direction": direction,
                    })
                queue.append((nt, other, d + 1))
    return {
        "root": {"type": type_name, "id": object_id},
        "nodes": nodes,
        "edges": edges,
        "depth": depth,
    }


def search_objects(type_name: str, predicate) -> List[OntologyObject]:
    return [o for o in list_objects(type_name, limit=1000) if predicate(o)][:50]


def call_function(name: str, **kwargs) -> Dict[str, Any]:
    for fn in ONTO["functions"]:
        if fn.name == name:
            return fn.handler(**kwargs)
    raise ValueError(f"Function {name} not found")
