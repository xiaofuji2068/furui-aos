# -*- coding: utf-8 -*-
"""TASK-002 #12：本体图补核电巡检实体（区域/监测站/指标/巡检记录 + 关联 + 巡检归因 Function）。"""
P = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\ontology\__init__.py"
with open(P, "r", encoding="utf-8") as f:
    src = f.read()

# ---- 1) 新增类型声明 ----
old_types = '''    customer_t = ObjectType("Customer", "客户主数据")
    order_t = ObjectType("Order", "销售订单")
    device_t = ObjectType("Device", "设备")
    product_t = ObjectType("Product", "产品")
    workorder_t = ObjectType("WorkOrder", "工单")
    ticket_t = ObjectType("Ticket", "事件 / 风险")'''
new_types = '''    customer_t = ObjectType("Customer", "客户主数据")
    order_t = ObjectType("Order", "销售订单")
    device_t = ObjectType("Device", "设备")
    product_t = ObjectType("Product", "产品")
    workorder_t = ObjectType("WorkOrder", "工单")
    ticket_t = ObjectType("Ticket", "事件 / 风险")
    # 核电巡检实体（TASK-002：监测站/设备 + 厂房区域 + 指标 + 巡检记录）
    station_t = ObjectType("MonitoringStation", "辐射监测站")
    area_t = ObjectType("Area", "厂房区域")
    metric_t = ObjectType("MetricRecord", "设备指标读数")
    inspection_t = ObjectType("InspectionRecord", "巡检记录")'''
assert old_types in src, "types anchor missing"
src = src.replace(old_types, new_types, 1)

# ---- 2) 在 Ticket 数据后插入核电实体数据 ----
old_ticket = '''    ticket_t.upsert(OntologyObject(type="Ticket", id="T-002", properties={
        "id": "T-002", "title": "三维建模交付数据质量告警", "severity": "medium", "category": "质量风险"
    }))
'''
new_ticket = '''    ticket_t.upsert(OntologyObject(type="Ticket", id="T-002", properties={
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
'''
assert old_ticket in src, "ticket anchor missing"
src = src.replace(old_ticket, new_ticket, 1)

# ---- 3) 补 Link ----
old_links = '''        OntologyLink(type="TicketToWorkOrder", source_id="T-002", target_id="WO-002"),
    ]'''
new_links = '''        OntologyLink(type="TicketToWorkOrder", source_id="T-002", target_id="WO-002"),
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
    ]'''
assert old_links in src, "links anchor missing"
src = src.replace(old_links, new_links, 1)

# ---- 4) 补 Function：巡检异常归因 ----
old_fn = '''        OntologyFunction(
            name="draft_report",'''
new_fn = '''        OntologyFunction(
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
            name="draft_report",'''
assert old_fn in src, "fn anchor missing"
src = src.replace(old_fn, new_fn, 1)

# ---- 5) return types 补新类型 ----
old_ret = '''        "types": {
            "Customer": customer_t, "Order": order_t, "Device": device_t,
            "Product": product_t, "WorkOrder": workorder_t, "Ticket": ticket_t,
        },'''
new_ret = '''        "types": {
            "Customer": customer_t, "Order": order_t, "Device": device_t,
            "Product": product_t, "WorkOrder": workorder_t, "Ticket": ticket_t,
            "MonitoringStation": station_t, "Area": area_t,
            "MetricRecord": metric_t, "InspectionRecord": inspection_t,
        },'''
assert old_ret in src, "return anchor missing"
src = src.replace(old_ret, new_ret, 1)

# ---- 6) 加 Function handler ----
old_handler = '''def _fn_create_workorder(title: str, priority: str = "medium") -> Dict[str, Any]:'''
new_handler = '''def _fn_analyze_inspection(month: str = "2026-08") -> Dict[str, Any]:
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


def _fn_create_workorder(title: str, priority: str = "medium") -> Dict[str, Any]:'''
assert old_handler in src, "handler anchor missing"
src = src.replace(old_handler, new_handler, 1)

with open(P, "w", encoding="utf-8") as f:
    f.write(src)
print("ONTOLOGY PATCH OK")
