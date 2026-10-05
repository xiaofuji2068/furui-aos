# -*- coding: utf-8 -*-
"""TASK-002 工具层补丁：tool_gateway.py 新增核电巡检工具集。"""
P = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\tool_gateway.py"
with open(P, "r", encoding="utf-8") as f:
    src = f.read()

changed = []

# ---------- 1. import 增加 InspectionWorkOrder ----------
old_imp = "from .models_ai import (\n    ActionReceipt, Agent, AgentTask, Approval, ApprovalRule, DataSource, Notification,\n    SalesTask, Tool, ToolExecution, write_audit,\n)"
new_imp = "from .models_ai import (\n    ActionReceipt, Agent, AgentTask, Approval, ApprovalRule, DataSource, InspectionWorkOrder,\n    Notification, SalesTask, Tool, ToolExecution, write_audit,\n)"
assert old_imp in src, "import block missing"
src = src.replace(old_imp, new_imp)
changed.append("import")

# ---------- 2. 工具实现：插在 _t_draft_report 之前 ----------
anchor = "def _esc(s: str) -> str:"
new_tools = '''def _t_query_monitoring_stations(ctx: ToolContext, p: Dict[str, Any]) -> Dict[str, Any]:
    """查询核电监测站台账（TASK-002 巡检场景）。"""
    area = p.get("area") or ""
    status = p.get("status") or ""
    where = []
    if area:
        where.append(f"area = '{_esc(area)}'")
    if status:
        where.append(f"status = '{_esc(status)}'")
    w = (" WHERE " + " AND ".join(where)) if where else ""
    sql = f"SELECT code, name, area, station_type, status, install_date FROM monitoring_stations{w} ORDER BY code"
    r = gw_query(sql, allowed_tables=_ds_tables(ctx, "IoT"))
    return {"summary": f"共 {r['row_count']} 个监测站", **r}


def _t_query_device_metrics(ctx: ToolContext, p: Dict[str, Any]) -> Dict[str, Any]:
    """查询设备指标读数（辐射 / 温度 / 振动）。"""
    station = p.get("station_code") or ""
    metric = p.get("metric") or ""
    month = p.get("month") or ""
    where = []
    if station:
        where.append(f"s.code = '{_esc(station)}'")
    if metric:
        where.append(f"m.metric = '{_esc(metric)}'")
    if month:
        where.append(f"substr(m.metric_date,1,7) = '{_esc(month)}'")
    w = (" WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT s.code AS station_code, s.name AS station_name, s.area,
               m.metric, m.metric_date, m.value, m.unit, m.threshold, m.status
        FROM device_metrics m
        JOIN monitoring_stations s ON s.id = m.station_id
        {w}
        ORDER BY m.metric_date DESC, s.code
    """
    r = gw_query(sql, allowed_tables=_ds_tables(ctx, "IoT", extra=("monitoring_stations",)))
    return {"summary": f"共 {r['row_count']} 条设备指标", **r}


def _t_analyze_inspection_anomaly(ctx: ToolContext, p: Dict[str, Any]) -> Dict[str, Any]:
    """核电巡检异常归因 — 用 SQL 把「站点 / 指标 / 环比」三维度真实算出来。

    与销售归因同构：不靠 LLM 拍脑袋，数字全部可复核。
    """
    curr, prev = "2026-08", "2026-07"           # 巡检样例数据固定为 7/8 月对比
    tables = _ds_tables(ctx, "IoT")

    # ① 总览：异常站点数
    ov = gw_query(
        f"""SELECT substr(m.metric_date,1,7) AS ym,
                   COUNT(DISTINCT CASE WHEN m.status='alarm' THEN s.code END) AS alarm_stations,
                   COUNT(DISTINCT s.code) AS total_stations
            FROM device_metrics m JOIN monitoring_stations s ON s.id = m.station_id
            WHERE substr(m.metric_date,1,7) IN ('{prev}','{curr}')
            GROUP BY ym ORDER BY ym""",
        allowed_tables=tables)
    m = {r["ym"]: r for r in ov["rows"]}

    # ② 指标维度：哪个指标、哪个站超限
    alarms = gw_query(
        f"""SELECT s.code AS station_code, s.name AS station_name, s.area,
                   m.metric, m.metric_date, m.value, m.unit, m.threshold,
                   ROUND((m.value - m.threshold) / m.threshold * 100, 1) AS over_pct
            FROM device_metrics m JOIN monitoring_stations s ON s.id = m.station_id
            WHERE m.status = 'alarm' AND substr(m.metric_date,1,7) = '{curr}'
            ORDER BY over_pct DESC""",
        allowed_tables=tables)

    # ③ 环比维度：7 月 → 8 月变化率
    delta = gw_query(
        f"""SELECT s.code AS station_code, m.metric,
                   MAX(CASE WHEN substr(m.metric_date,1,7)='{prev}' THEN m.value END) AS prev_value,
                   MAX(CASE WHEN substr(m.metric_date,1,7)='{curr}' THEN m.value END) AS curr_value,
                   m.unit, m.threshold
            FROM device_metrics m JOIN monitoring_stations s ON s.id = m.station_id
            WHERE m.metric_date IN (SELECT MAX(metric_date) FROM device_metrics WHERE substr(metric_date,1,7) IN ('{prev}','{curr}'))
            GROUP BY s.code, m.metric, m.unit, m.threshold""",
        allowed_tables=tables)
    deltas = []
    for r in delta["rows"]:
        if r["prev_value"] and r["curr_value"]:
            chg = round((r["curr_value"] - r["prev_value"]) / r["prev_value"] * 100, 1)
            deltas.append({**r, "change_pct": chg})

    top = None
    if alarms["rows"]:
        top = alarms["rows"][0]

    return {
        "months": {"current": curr, "previous": prev},
        "overview": {
            "current": m.get(curr, {}), "previous": m.get(prev, {}),
            "alarm_stations_curr": m.get(curr, {}).get("alarm_stations", 0),
        },
        "alarm_dimension": alarms["rows"],
        "top_alarm": top,
        "delta_dimension": deltas,
        "_sql": {"overview": ov["sql"]},
    }


def _t_create_workorder(ctx: ToolContext, p: Dict[str, Any]) -> Dict[str, Any]:
    """创建核电巡检工单（写入动作，Level 3 必须审批）。"""
    wo = InspectionWorkOrder(
        company_id=ctx.company_id,
        station_code=p.get("station_code") or "",
        station_name=p.get("station_name") or "",
        title=p.get("title") or "",
        detail=p.get("detail") or "",
        priority=p.get("priority") or "high",
        owner=p.get("owner") or "",
        due_date=p.get("due_date") or "",
        status="待处置",
        source="agent",
        agent_id=ctx.agent.id if ctx.agent else None,
        approval_id=p.get("_approval_id"),
        created_by=ctx.user.name if ctx.user else "system",
    )
    ctx.db.add(wo)
    ctx.db.flush()
    return {"ok": True, "workorder_id": wo.id, "title": wo.title,
            "station_code": wo.station_code, "owner": wo.owner, "due_date": wo.due_date}


def _esc(s: str) -> str:'''
assert anchor in src, "esc anchor missing"
src = src.replace(anchor, new_tools, 1)
changed.append("tools")

# ---------- 3. 注册表追加 4 个工具 ----------
old_impl = '''    "send_notification":   ToolImpl("send_notification",   "发送通知",         _t_send_notification, ["message"]),
    "draft_report":        ToolImpl("draft_report",        "草拟分析报告",     _t_draft_report, ["topic"]),
}'''
new_impl = '''    "send_notification":   ToolImpl("send_notification",   "发送通知",         _t_send_notification, ["message"]),
    "draft_report":        ToolImpl("draft_report",        "草拟分析报告",     _t_draft_report, ["topic"]),
    "query_monitoring_stations": ToolImpl("query_monitoring_stations", "查询核电监测站台账", _t_query_monitoring_stations),
    "query_device_metrics":      ToolImpl("query_device_metrics",      "查询设备指标读数",   _t_query_device_metrics),
    "analyze_inspection_anomaly": ToolImpl("analyze_inspection_anomaly", "巡检异常归因分析", _t_analyze_inspection_anomaly),
    "create_workorder":          ToolImpl("create_workorder",          "创建核电巡检工单",   _t_create_workorder, ["title"], default_level=3),
}'''
assert old_impl in src, "impl registry missing"
src = src.replace(old_impl, new_impl, 1)
changed.append("registry")

# ---------- 4. _approval_title 增加 create_workorder ----------
old_at = '''    if tool_name == "create_sales_task":
        who = params.get("customer_name") or "客户"
        return f"为 {who} 创建跟进任务「{params.get('title', '')}」"'''
new_at = '''    if tool_name == "create_sales_task":
        who = params.get("customer_name") or "客户"
        return f"为 {who} 创建跟进任务「{params.get('title', '')}」"
    if tool_name == "create_workorder":
        who = params.get("station_code") or params.get("station_name") or "监测站"
        return f"为 {who} 创建巡检工单「{params.get('title', '')}」"'''
assert old_at in src, "approval title anchor missing"
src = src.replace(old_at, new_at, 1)
changed.append("approval_title")

with open(P, "w", encoding="utf-8") as f:
    f.write(src)
print("TOOL PATCH OK:", changed)
