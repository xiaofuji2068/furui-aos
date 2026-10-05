"""Tool Gateway（TASK-019 / TASK-020）+ 审批执行（TASK-021 / TASK-022）。

清单硬性要求：
    Agent  →  Tool Gateway  →  权限验证 → 参数验证 → 审批判断 → 执行 → 日志
    禁止   Agent 直接调用生产 API

本模块是所有 Agent 动作的唯一出口。工具实现只关心"怎么查"，
权限、审批、日志由网关统一兜住 —— 任何绕过网关的调用都不存在。

动作分级（TASK-021）：
    Level 1 自动执行      查询数据、知识检索、生成草稿
    Level 2 通知后执行    创建内部任务、生成报告
    Level 3 必须审批      创建客户任务、发送外部通知、修改业务数据
    Level 4 禁止执行      删除核心数据、大额资金操作
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from .data_gateway import GatewayError, query as gw_query
from .models import User
from .models_ai import (
    ActionReceipt, Agent, AgentTask, Approval, ApprovalRule, DataSource, InspectionWorkOrder,
    Notification, SalesTask, Tool, ToolExecution, write_audit,
)
from .rag import search as rag_search


@dataclass
class ToolContext:
    """一次工具调用的完整上下文 — 权限与审计都依赖它。"""
    db: Session
    agent: Optional[Agent] = None
    user: Optional[User] = None
    company_id: int = 0
    task_id: Optional[int] = None
    step_id: Optional[int] = None

    @property
    def actor_name(self) -> str:
        if self.agent:
            return f"Agent:{self.agent.name}"
        return self.user.name if self.user else "system"


# ==================== 数据月份自动推导 ====================

def recent_months() -> tuple[str, str]:
    """从数据里推导「最新月 / 上月」，避免硬编码月份过期。"""
    r = gw_query("SELECT DISTINCT substr(order_date,1,7) AS ym FROM orders ORDER BY ym DESC LIMIT 2")
    months = [row["ym"] for row in r["rows"]]
    if len(months) >= 2:
        return months[0], months[1]
    if len(months) == 1:
        return months[0], months[0]
    return "", ""


# ==================== 工具实现 ====================

def _t_query_erp_orders(ctx: ToolContext, p: Dict[str, Any]) -> Dict[str, Any]:
    month = p.get("month") or ""
    region = p.get("region") or ""
    customer = p.get("customer_name") or ""

    where = []
    if month:
        where.append(f"substr(o.order_date,1,7) = '{_esc(month)}'")
    if region:
        where.append(f"o.region = '{_esc(region)}'")
    if customer:
        where.append(f"c.name LIKE '%{_esc(customer)}%'")
    w = (" WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
        SELECT o.order_no, o.order_date, c.name AS customer, p.name AS product,
               o.region, o.qty, o.amount, o.status
        FROM orders o
        JOIN customers c ON c.id = o.customer_id
        JOIN products  p ON p.id = o.product_id
        {w}
        ORDER BY o.order_date DESC
    """
    # 订单要展示客户名，需 JOIN customers —— 显式声明跨类别依赖（仍受 Agent 授权范围约束）
    r = gw_query(sql, allowed_tables=_ds_tables(ctx, "ERP", extra=("customers",)))
    return {"summary": f"共 {r['row_count']} 笔订单", **r}


def _t_query_crm_customers(ctx: ToolContext, p: Dict[str, Any]) -> Dict[str, Any]:
    level = p.get("level") or ""
    region = p.get("region") or ""
    name = p.get("name") or ""

    where = []
    if level:
        where.append(f"level = '{_esc(level)}'")
    if region:
        where.append(f"region = '{_esc(region)}'")
    if name:
        where.append(f"name LIKE '%{_esc(name)}%'")
    w = (" WHERE " + " AND ".join(where)) if where else ""

    sql = f"SELECT id, name, level, region, industry, contact_name, contact_phone FROM customers{w} ORDER BY level, name"
    r = gw_query(sql, allowed_tables=_ds_tables(ctx, "CRM"))
    return {"summary": f"共 {r['row_count']} 家客户", **r}


def _t_search_knowledge(ctx: ToolContext, p: Dict[str, Any]) -> Dict[str, Any]:
    q = p.get("query") or ""
    top_k = int(p.get("top_k") or 5)
    kb_ids = ctx.agent.knowledge_ids if ctx.agent else None
    dept_id = ctx.user.department_id if ctx.user else None
    r = rag_search(ctx.db, q, company_id=ctx.company_id,
                   kb_ids=kb_ids, department_id=dept_id, top_k=top_k)
    return {"summary": f"命中 {len(r['hits'])} 条知识", **r}


def _t_analyze_sales_drop(ctx: ToolContext, p: Dict[str, Any]) -> Dict[str, Any]:
    """销售下降归因 — 严格按《销售异常归因标准指引》的四步法执行。

    这不是让 LLM 拍脑袋，而是用 SQL 把三个维度真实算出来，
    LLM 只负责把算出来的事实组织成结论。数字必须可复核。
    """
    curr, prev = recent_months()
    if not curr or not prev:
        return {"error": "订单数据不足，无法做环比分析"}

    tables = _ds_tables(ctx, "ERP") | _ds_tables(ctx, "CRM")

    # ① 总览
    ov = gw_query(
        f"""SELECT substr(order_date,1,7) AS ym, COUNT(*) AS cnt, ROUND(SUM(amount)/10000,2) AS amt_wan
            FROM orders WHERE substr(order_date,1,7) IN ('{prev}','{curr}')
            GROUP BY ym ORDER BY ym""",
        allowed_tables=tables)
    m = {r["ym"]: r for r in ov["rows"]}
    if prev not in m or curr not in m:
        return {"error": f"缺少 {prev} 或 {curr} 的完整数据"}
    d_cnt = m[curr]["cnt"] - m[prev]["cnt"]
    d_amt = m[curr]["amt_wan"] - m[prev]["amt_wan"]
    pct = round(d_amt / m[prev]["amt_wan"] * 100, 1) if m[prev]["amt_wan"] else 0

    # ② 客户维度：谁的贡献下滑最多
    cust = gw_query(
        f"""SELECT c.name, c.level,
                   SUM(CASE WHEN substr(o.order_date,1,7)='{prev}' THEN o.amount ELSE 0 END)/10000 AS prev_wan,
                   SUM(CASE WHEN substr(o.order_date,1,7)='{curr}' THEN o.amount ELSE 0 END)/10000 AS curr_wan,
                   SUM(CASE WHEN substr(o.order_date,1,7)='{prev}' THEN 1 ELSE 0 END) AS prev_cnt,
                   SUM(CASE WHEN substr(o.order_date,1,7)='{curr}' THEN 1 ELSE 0 END) AS curr_cnt
            FROM orders o JOIN customers c ON c.id = o.customer_id
            WHERE substr(o.order_date,1,7) IN ('{prev}','{curr}')
            GROUP BY c.id ORDER BY (prev_wan - curr_wan) DESC""",
        allowed_tables=tables)

    top_drop = None
    for r in cust["rows"]:
        delta = round(r["prev_wan"] - r["curr_wan"], 2)
        if delta > 0:
            top_drop = {**r, "delta_wan": delta,
                        "share": round(delta / abs(d_amt) * 100, 1) if d_amt else 0}
            break

    # ③ 价格维度
    price = gw_query(
        f"""SELECT p.name AS product,
                   ROUND(AVG(CASE WHEN substr(o.order_date,1,7)='{prev}' THEN o.amount/o.qty END),0) AS prev_price,
                   ROUND(AVG(CASE WHEN substr(o.order_date,1,7)='{curr}' THEN o.amount/o.qty END),0) AS curr_price,
                   COUNT(*) AS cnt
            FROM orders o JOIN products p ON p.id = o.product_id
            WHERE substr(o.order_date,1,7) IN ('{prev}','{curr}')
            GROUP BY p.id""",
        allowed_tables=tables)
    price_moves = []
    for r in price["rows"]:
        if r["prev_price"] and r["curr_price"]:
            chg = round((r["curr_price"] - r["prev_price"]) / r["prev_price"] * 100, 1)
            if abs(chg) >= 5:
                price_moves.append({**r, "change_pct": chg})

    # ④ 新客维度
    newc = gw_query(
        f"""SELECT substr(first_day,1,7) AS ym, COUNT(*) AS new_customers
            FROM (SELECT customer_id, MIN(order_date) AS first_day FROM orders GROUP BY customer_id)
            GROUP BY ym ORDER BY ym DESC LIMIT 3""",
        allowed_tables=tables)
    new_map = {r["ym"]: r["new_customers"] for r in newc["rows"]}

    return {
        "months": {"current": curr, "previous": prev},
        "overview": {
            "previous": m[prev], "current": m[curr],
            "delta_cnt": d_cnt, "delta_amt_wan": round(d_amt, 2), "pct": pct,
        },
        "customer_dimension": cust["rows"],
        "top_drop_customer": top_drop,
        "price_moves": price_moves,
        "new_customers": new_map,
        "new_curr": new_map.get(curr, 0),
        "new_prev": new_map.get(prev, 0),
        "_sql": {"overview": ov["sql"]},
    }


def _t_create_sales_task(ctx: ToolContext, p: Dict[str, Any]) -> Dict[str, Any]:
    """在 CRM 中创建销售跟进任务（写入动作，Level 3 必须审批）。"""
    task = SalesTask(
        company_id=ctx.company_id,
        customer_id=p.get("customer_id"),
        customer_name=p.get("customer_name") or "",
        title=p.get("title") or "",
        detail=p.get("detail") or "",
        priority=p.get("priority") or "high",
        owner=p.get("owner") or "",
        due_date=p.get("due_date") or "",
        status="待跟进",
        source="agent",
        agent_id=ctx.agent.id if ctx.agent else None,
        approval_id=p.get("_approval_id"),
        created_by=ctx.user.name if ctx.user else "system",
    )
    ctx.db.add(task)
    ctx.db.flush()
    return {"ok": True, "sales_task_id": task.id, "title": task.title,
            "owner": task.owner, "due_date": task.due_date}


def _t_send_notification(ctx: ToolContext, p: Dict[str, Any]) -> Dict[str, Any]:
    ntype = p.get("channel") or "system"
    message = p.get("message") or ""
    n = Notification(
        company_id=ctx.company_id,
        user_id=ctx.user.id if ctx.user else None,
        ntype=ntype,
        title=p.get("title") or "Agent 通知",
        content=message,
        status="Unread",
    )
    ctx.db.add(n)
    ctx.db.flush()
    return {"ok": True, "notification_id": n.id, "channel": ntype, "message": message}


def _t_draft_report(ctx: ToolContext, p: Dict[str, Any]) -> Dict[str, Any]:
    topic = p.get("topic") or ""
    audience = p.get("audience") or "管理层"
    content = p.get("content") or ""
    return {
        "ok": True,
        "topic": topic,
        "audience": audience,
        "format": "markdown",
        "content": content,
        "char_count": len(content),
    }


def _t_query_monitoring_stations(ctx: ToolContext, p: Dict[str, Any]) -> Dict[str, Any]:
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


def _esc(s: str) -> str:
    """防 SQL 注入：转义单引号。网关还有白名单兜底，这里是第一道。"""
    return str(s).replace("'", "''")


def _ds_tables(ctx: ToolContext, category: str, extra: tuple = ()) -> set:
    """该 Agent 被授权访问的表集合。

    安全边界 = 「Agent 被授权的数据源」∩「这些数据源声明的 allowed_tables」。
    默认只放开指定类别（如 ERP）的表；工具若确实需要跨类别 JOIN（如订单 JOIN 客户主数据），
    必须显式声明在 extra 里，且该表仍必须落在 Agent 已授权的数据源范围内 —— 声明不等于放行。
    """
    ids = ctx.agent.datasource_ids if ctx.agent else []
    if not ids:
        return set()
    rows = ctx.db.query(DataSource).filter(DataSource.id.in_(ids)).all()

    scoped: set = set()
    authorized: set = set()
    for r in rows:
        authorized |= set(r.tables)
        if r.category == category:
            scoped |= set(r.tables)

    # 跨类别声明：只取 Agent 本身就有权限的那部分
    return scoped | (set(extra) & authorized)


# ==================== 工具注册表 ====================

@dataclass
class ToolImpl:
    name: str
    label: str
    run: Callable[[ToolContext, Dict[str, Any]], Dict[str, Any]]
    required_params: List[str] = field(default_factory=list)
    default_level: int = 1


IMPL: Dict[str, ToolImpl] = {
    "query_erp_orders":    ToolImpl("query_erp_orders",    "查询 ERP 销售订单", _t_query_erp_orders),
    "query_crm_customers": ToolImpl("query_crm_customers", "查询 CRM 客户信息", _t_query_crm_customers),
    "search_knowledge":    ToolImpl("search_knowledge",    "检索企业知识库",   _t_search_knowledge, ["query"]),
    "analyze_sales_drop":  ToolImpl("analyze_sales_drop",  "销售下降归因分析", _t_analyze_sales_drop),
    "create_sales_task":   ToolImpl("create_sales_task",   "创建销售跟进任务", _t_create_sales_task, ["title"]),
    "send_notification":   ToolImpl("send_notification",   "发送通知",         _t_send_notification, ["message"]),
    "draft_report":        ToolImpl("draft_report",        "草拟分析报告",     _t_draft_report, ["topic"]),
    "query_monitoring_stations": ToolImpl("query_monitoring_stations", "查询核电监测站台账", _t_query_monitoring_stations),
    "query_device_metrics":      ToolImpl("query_device_metrics",      "查询设备指标读数",   _t_query_device_metrics),
    "analyze_inspection_anomaly": ToolImpl("analyze_inspection_anomaly", "巡检异常归因分析", _t_analyze_inspection_anomaly),
    "create_workorder":          ToolImpl("create_workorder",          "创建核电巡检工单",   _t_create_workorder, ["title"], default_level=3),
}


# ==================== 网关执行（TASK-020） ====================

def _resolve_level(db: Session, tool: Tool, company_id: int) -> int:
    """审批级别：规则表优先，回退工具定义。"""
    rule = (db.query(ApprovalRule)
            .filter(ApprovalRule.company_id == company_id,
                    ApprovalRule.action == tool.name,
                    ApprovalRule.enabled.is_(True)).first())
    return rule.level if rule else tool.action_level


def _hash(obj: Any) -> str:
    """稳定 sha256 摘要（排序键 + 统一中文编码，保证同参同哈希）。"""
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _write_receipt(db, *, company_id, approval_id, tool_name,
                    params, result, actor_type="agent", actor_id=None) -> int:
    """写入动作执行凭证（图谱 Receipt）：params/result 哈希，事后可复算核验。

    返回 receipt id（门禁校验用：写回动作必须留下凭证才算完成）。
    """
    rc = ActionReceipt(
        company_id=company_id, approval_id=approval_id, tool_name=tool_name,
        params_hash=_hash(params), result_hash=_hash(result),
        actor_type=actor_type, actor_id=actor_id,
    )
    db.add(rc)
    db.flush()
    return rc.id


def _require_receipt(db, receipt_id: int, *, approval_id, tool_name) -> bool:
    """写回门禁校验（图谱 Receipt）：执行成功后凭证必须真实存在。

    这是"强制留痕"的兜底断言——任何经网关真实执行的动作，
    若事后查不到 Receipt，即视为未完成（审计链断裂），返回 False。
    """
    rc = db.get(ActionReceipt, receipt_id)
    if rc is None:
        return False
    if approval_id is not None and rc.approval_id != approval_id:
        return False
    if rc.tool_name != tool_name:
        return False
    return True


def execute(ctx: ToolContext, tool_name: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """经网关执行一次工具调用。

    返回三种形态：
      {"ok": True,  "result": ...}                       已执行
      {"ok": False, "blocked": True, "approval_id": n}   待人工审批（Level 3）
      {"ok": False, "error": "...", "reason": ...}       被拒绝
    """
    params = params or {}
    db = ctx.db
    started = time.time()

    tool = db.query(Tool).filter(Tool.company_id == ctx.company_id, Tool.name == tool_name).first()
    if not tool:
        return {"ok": False, "error": f"工具 {tool_name} 不存在", "reason": "tool_not_found"}
    if tool.status != "active":
        return {"ok": False, "error": f"工具 {tool_name} 已停用", "reason": "tool_disabled"}
    impl = IMPL.get(tool_name)
    if not impl:
        return {"ok": False, "error": f"工具 {tool_name} 无实现", "reason": "no_impl"}

    # ---- 闸门 1：Agent 工具白名单 ----
    if ctx.agent is not None and tool.id not in ctx.agent.tool_ids:
        _log(db, ctx, tool, params, status="blocked", permission="denied",
             error="该 Agent 未获授权调用此工具", ms=started)
        write_audit(db, action="tool.call", actor_type="agent",
                    actor_id=ctx.agent.id if ctx.agent else None, actor_name=ctx.actor_name,
                    company_id=ctx.company_id, target=tool_name,
                    detail={"params": params, "reason": "agent_tool_not_allowed"},
                    result="denied")
        db.commit()
        return {"ok": False, "error": "该 Agent 未获授权调用此工具", "reason": "agent_not_allowed"}

    # ---- 闸门 2：用户权限点 ----
    if ctx.user is not None and tool.required_permission and not ctx.user.has_perm(tool.required_permission):
        _log(db, ctx, tool, params, status="blocked", permission="denied",
             error=f"当前用户缺少权限 {tool.required_permission}", ms=started)
        write_audit(db, action="tool.call", actor_type="agent",
                    actor_id=ctx.agent.id if ctx.agent else None, actor_name=ctx.actor_name,
                    company_id=ctx.company_id, target=tool_name,
                    detail={"params": params, "reason": "user_permission_missing"},
                    result="denied")
        db.commit()
        return {"ok": False, "error": f"当前用户缺少权限：{tool.required_permission}", "reason": "user_denied"}

    # ---- 闸门 3：参数校验 ----
    missing = [k for k in impl.required_params if not params.get(k)]
    if missing:
        return {"ok": False, "error": f"缺少必填参数：{', '.join(missing)}", "reason": "missing_params"}

    # ---- 闸门 4：审批判断（TASK-021）----
    level = _resolve_level(db, tool, ctx.company_id)
    if level == 4:
        _log(db, ctx, tool, params, status="blocked", permission="pass",
             error="该动作被列为 Level 4，禁止 AI 执行", ms=started)
        write_audit(db, action="tool.call", actor_type="agent", actor_name=ctx.actor_name,
                    company_id=ctx.company_id, target=tool_name,
                    detail={"params": params, "reason": "level4_forbidden"}, result="denied")
        db.commit()
        return {"ok": False, "error": "该动作属于 Level 4，禁止 AI 执行", "reason": "forbidden"}

    if level == 3:
        ap = Approval(
            company_id=ctx.company_id,
            task_id=ctx.task_id, step_id=ctx.step_id,
            agent_id=ctx.agent.id if ctx.agent else None,
            title=f"{tool.label}：{_approval_title(tool_name, params)}",
            action=tool_name, level=level,
            ai_reason=params.get("_reason") or "",
            data_evidence=json.dumps(params.get("_evidence") or {}, ensure_ascii=False),
            plan=json.dumps(params.get("_plan") or {}, ensure_ascii=False),
            payload=json.dumps(params, ensure_ascii=False),
            status="Pending",
        )
        db.add(ap)
        db.flush()
        _log(db, ctx, tool, params, status="pending_approval", permission="pass",
             output={"approval_id": ap.id}, ms=started)
        db.add(Notification(
            company_id=ctx.company_id, user_id=ctx.user.id if ctx.user else None,
            ntype="approval", title="待确认：AI 请求执行写入动作",
            content=ap.title, ref_id=ap.id, status="Unread"))
        write_audit(db, action="approval.create", actor_type="agent", actor_name=ctx.actor_name,
                    company_id=ctx.company_id, target=tool_name,
                    detail={"approval_id": ap.id, "params": params}, result="success")
        db.commit()
        return {"ok": False, "blocked": True, "approval_id": ap.id,
                "message": "该动作需人工审批，已生成审批单", "level": 3}

    # ---- 闸门 5：执行 ----
    try:
        result = impl.run(ctx, params)
        status = "success"
        error = ""
    except GatewayError as e:
        result, status, error = {}, "failed", str(e)
    except Exception as e:                                    # noqa: BLE001
        result, status, error = {}, "failed", f"{type(e).__name__}: {e}"
        db.rollback()

    # Level 2：执行后通知
    if status == "success" and level == 2:
        db.add(Notification(
            company_id=ctx.company_id, user_id=ctx.user.id if ctx.user else None,
            ntype="agent_task", title=f"AI 已执行：{tool.label}",
            content=str(result)[:300], status="Unread"))

    _log(db, ctx, tool, params, status=status, permission="pass",
         output=result, error=error, ms=started)
    write_audit(db, action="tool.call", actor_type="agent",
                actor_id=ctx.agent.id if ctx.agent else None, actor_name=ctx.actor_name,
                company_id=ctx.company_id, target=tool_name,
                detail={"params": params, "level": level}, result=status)
    if status == "success":
        receipt_id = _write_receipt(
            db, company_id=ctx.company_id,
            approval_id=params.get("_approval_id"), tool_name=tool_name,
            params=params, result=result,
            actor_type="agent", actor_id=ctx.agent.id if ctx.agent else None,
        )
        # 写回门禁校验：凭证必须真实存在，否则执行不成立（审计链断裂）
        if not _require_receipt(db, receipt_id,
                                approval_id=params.get("_approval_id"),
                                tool_name=tool_name):
            db.rollback()
            return {"ok": False, "error": "执行成功但 Receipt 落库失败，动作已回滚",
                    "reason": "receipt_missing"}
        db.flush()
        receipt_id_out = receipt_id
    else:
        receipt_id_out = None
    db.commit()

    if status == "failed":
        return {"ok": False, "error": error, "reason": "exec_failed"}
    return {"ok": True, "result": result, "level": level, "tool": tool.label,
            "receipt_id": receipt_id_out}


def _approval_title(tool_name: str, params: Dict[str, Any]) -> str:
    if tool_name == "create_sales_task":
        who = params.get("customer_name") or "客户"
        return f"为 {who} 创建跟进任务「{params.get('title', '')}」"
    if tool_name == "create_workorder":
        who = params.get("station_code") or params.get("station_name") or "监测站"
        return f"为 {who} 创建巡检工单「{params.get('title', '')}」"
    if tool_name == "send_notification":
        return f"发送通知至 {params.get('channel', '默认渠道')}"
    return params.get("title") or tool_name


def _log(db, ctx: ToolContext, tool: Tool, params, *, status, permission,
         output=None, error="", ms: float) -> ToolExecution:
    rec = ToolExecution(
        company_id=ctx.company_id,
        tool_id=tool.id,
        agent_id=ctx.agent.id if ctx.agent else None,
        task_id=ctx.task_id,
        user_id=ctx.user.id if ctx.user else None,
        tool_name=tool.name,
        input_data=json.dumps(params, ensure_ascii=False)[:4000],
        output_data=json.dumps(output or {}, ensure_ascii=False)[:4000],
        status=status, error=error, permission_check=permission,
        duration_ms=int((time.time() - ms) * 1000),
    )
    db.add(rec)
    db.flush()
    return rec


# ==================== 审批处理（TASK-022） ====================

def _decision_input_hash(ap: Approval) -> str:
    """决策输入指纹（图谱 #5 lineage）：理由 + 数据依据 + 执行计划 + 参数。"""
    return _hash({
        "ai_reason": ap.ai_reason or "",
        "data_evidence": ap.data_evidence or "{}",
        "plan": ap.plan or "{}",
        "payload": ap.payload or "{}",
    })


def _write_lineage(db, ap: Approval, *, decision: str, result=None,
                   receipt_id=None) -> None:
    """写决策溯源（Approval.decision_lineage）：输入/输出哈希 + 决策人/时间。

    事后可复算：对同一审批单的证据域重算 input_hash 即可核验决策未被篡改。
    """
    lineage = {
        "decision": decision,
        "decided_by": ap.decided_by or "",
        "decided_at": ap.decided_at.isoformat() if ap.decided_at else "",
        "comment": ap.comment or "",
        "input_hash": _decision_input_hash(ap),
    }
    if result is not None:
        lineage["output_hash"] = _hash(result)
    if receipt_id is not None:
        lineage["receipt_id"] = receipt_id
    ap.decision_lineage = json.dumps(lineage, ensure_ascii=False, default=str)


def _sync_task_on_decision(db: Session, ap: Approval, target: str, comment: str) -> None:
    """TASK-012：审批决策后同步关联 AgentTask 状态（WaitingApproval → Completed / Returned）。

    审批是长程任务状态的驱动事件：批准执行成功则任务完成，
    拒绝则任务退回（Returned），后续可重跑或人工介入。
    """
    if not ap.task_id:
        return
    t = db.query(AgentTask).filter(AgentTask.id == ap.task_id).first()
    if t is None:
        return
    if t.status != "WaitingApproval":
        return
    if t.transition(target):
        if target == "Completed":
            t.finished_at = datetime.utcnow()
        else:
            t.error = f"审批被拒绝：{comment or '未填写意见'}"
        write_audit(db, action="task.review", actor_type="system",
                    company_id=ap.company_id, target=f"task#{t.id}",
                    detail={"decision": target, "approval_id": ap.id, "comment": comment},
                    result="success")


def decide_approval(db: Session, approval_id: int, *, user: User,
                    decision: str, comment: str = "",
                    modified_payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """批准 / 拒绝 / 修改后执行。

    decision: approve / reject
    批准后按 payload（可被人工修改）真正执行动作。
    """
    ap = db.query(Approval).filter(Approval.id == approval_id).first()
    if not ap:
        return {"ok": False, "error": "审批单不存在"}
    if ap.status != "Pending":
        return {"ok": False, "error": f"审批单已处理（{ap.status}）"}

    if not user.has_perm("approval:approve"):
        write_audit(db, action="approval.decide", actor_type="user", actor_id=user.id,
                    actor_name=user.name, company_id=ap.company_id,
                    target=f"approval#{approval_id}", detail={"decision": decision}, result="denied")
        db.commit()
        return {"ok": False, "error": "当前用户无审批权限"}

    ap.decided_by = user.name
    ap.decided_at = datetime.utcnow()
    ap.comment = comment

    if decision == "reject":
        ap.status = "Rejected"
        _write_lineage(db, ap, decision="reject")
        write_audit(db, action="approval.reject", actor_type="user", actor_id=user.id,
                    actor_name=user.name, company_id=ap.company_id,
                    target=ap.action, detail={"approval_id": ap.id, "comment": comment},
                    result="success")
        # TASK-012 状态机闭环：审批拒绝 → 关联任务 WaitingApproval → Returned
        _sync_task_on_decision(db, ap, "Returned", comment)
        db.commit()
        return {"ok": True, "status": "Rejected", "approval_id": ap.id}

    # 批准（允许人工修改参数后再执行）
    params = modified_payload if modified_payload is not None else json.loads(ap.payload or "{}")
    params["_approval_id"] = ap.id
    ap.payload = json.dumps(params, ensure_ascii=False)

    agent = db.query(Agent).filter(Agent.id == ap.agent_id).first() if ap.agent_id else None
    ctx = ToolContext(db=db, agent=agent, user=user, company_id=ap.company_id,
                      task_id=ap.task_id, step_id=ap.step_id)

    tool = db.query(Tool).filter(Tool.company_id == ap.company_id, Tool.name == ap.action).first()
    impl = IMPL.get(ap.action)
    if not tool or not impl:
        ap.status = "Failed"
        db.commit()
        return {"ok": False, "error": "工具不可用"}

    started = time.time()
    try:
        result = impl.run(ctx, params)
        ap.status = "Executed"
        _log(db, ctx, tool, params, status="success", permission="pass",
             output=result, ms=started)
        write_audit(db, action="approval.execute", actor_type="user", actor_id=user.id,
                    actor_name=user.name, company_id=ap.company_id, target=ap.action,
                    detail={"approval_id": ap.id, "params": params}, result="success")
        receipt_id = _write_receipt(
            db, company_id=ap.company_id, approval_id=ap.id, tool_name=ap.action,
            params=params, result=result,
            actor_type="user", actor_id=user.id,
        )
        # 写回门禁校验：审批批准后的执行必须有凭证留痕
        if not _require_receipt(db, receipt_id, approval_id=ap.id, tool_name=ap.action):
            db.rollback()
            ap = db.query(Approval).filter(Approval.id == approval_id).first()
            if ap:
                ap.status = "Failed"
            db.commit()
            return {"ok": False, "error": "执行成功但 Receipt 落库失败，动作已回滚",
                    "reason": "receipt_missing"}
        _write_lineage(db, ap, decision="approve", result=result, receipt_id=receipt_id)
        # TASK-012 状态机闭环：审批执行成功 → 关联任务 WaitingApproval → Completed
        _sync_task_on_decision(db, ap, "Completed", comment)
        db.commit()
        return {"ok": True, "status": "Executed", "approval_id": ap.id,
                "result": result, "receipt_id": receipt_id}
    except Exception as e:                                     # noqa: BLE001
        db.rollback()
        ap = db.query(Approval).filter(Approval.id == approval_id).first()
        if ap:
            ap.status = "Failed"
        write_audit(db, action="approval.execute", actor_type="user", actor_id=user.id,
                    actor_name=user.name, company_id=ap.company_id if ap else None,
                    target=ap.action if ap else "", detail={"error": str(e)}, result="failed")
        db.commit()
        return {"ok": False, "error": str(e)}
