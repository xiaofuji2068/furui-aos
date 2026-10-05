"""数据源共享 store —— 首页 /api/overview 与 /api/data-sources 都从这里取数。

状态语义：
- connected    已连接、数据正常
- warning      已连接、但存在延迟/缺数等告警
- error        连接异常、需要排查
- disconnected 未连接

真实接入时，把 _SOURCES 换成从配置中心 / 健康检查服务拉取即可，接口形态不变。
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

# ---------- 初始数据源（内存） ----------

_SOURCES: List[Dict[str, Any]] = [
    {
        "id": "erp",
        "name": "ERP 系统",
        "icon": "📊",
        "tone": "blue",
        "category": "业务系统",
        "type": "jdbc",
        "status": "connected",
        "state": "数据正常",
        "last_sync": "2 分钟前",
        "records": "1,284,392",
        "latency_ms": 86,
        "health": 98,
        "desc": "企业资源计划主数据（订单 / 库存 / 财务）",
        "config": {"host": "10.0.3.21", "db": "erp_prod", "user": "aios_ro"},
    },
    {
        "id": "crm",
        "name": "CRM 系统",
        "icon": "👥",
        "tone": "violet",
        "category": "业务系统",
        "type": "api",
        "status": "connected",
        "state": "数据正常",
        "last_sync": "1 分钟前",
        "records": "486,201",
        "latency_ms": 54,
        "health": 99,
        "desc": "客户关系与销售机会数据",
        "config": {"endpoint": "https://crm.furui.internal/v2", "user": "aios"},
    },
    {
        "id": "mes",
        "name": "MES 系统",
        "icon": "🏭",
        "tone": "emerald",
        "category": "生产系统",
        "type": "jdbc",
        "status": "warning",
        "state": "同步延迟偏高",
        "last_sync": "17 分钟前",
        "records": "2,931,774",
        "latency_ms": 412,
        "health": 81,
        "desc": "制造执行系统（工单 / 工序 / 产出）",
        "config": {"host": "10.0.4.10", "db": "mes_prod", "user": "aios_ro"},
    },
    {
        "id": "iot",
        "name": "设备物联网",
        "icon": "📡",
        "tone": "sky",
        "category": "生产系统",
        "type": "mqtt",
        "status": "connected",
        "state": "数据正常",
        "last_sync": "刚刚",
        "records": "8,442,109",
        "latency_ms": 33,
        "health": 97,
        "desc": "设备传感器实时采集（温度 / 振动 / 电流）",
        "config": {"broker": "tcp://iot.furui.internal:1883"},
    },
    {
        "id": "kb",
        "name": "企业知识库",
        "icon": "📚",
        "tone": "amber",
        "category": "知识系统",
        "type": "vector",
        "status": "connected",
        "state": "数据正常",
        "last_sync": "5 分钟前",
        "records": "57,318",
        "latency_ms": 71,
        "health": 95,
        "desc": "企业文档 / 制度 / SOP 向量库",
        "config": {"index": "furui-kb", "dim": 1536},
    },
    {
        "id": "hr",
        "name": "HR 系统",
        "icon": "🧑‍💼",
        "tone": "rose",
        "category": "业务系统",
        "type": "api",
        "status": "disconnected",
        "state": "未连接",
        "last_sync": "—",
        "records": "0",
        "latency_ms": 0,
        "health": 0,
        "desc": "人力资源主数据（组织 / 员工 / 排班）",
        "config": {"endpoint": "https://hr.furui.internal/api", "user": "aios"},
    },
    {
        "id": "scm",
        "name": "供应链系统",
        "icon": "🔗",
        "tone": "cyan",
        "category": "业务系统",
        "type": "jdbc",
        "status": "error",
        "state": "连接异常",
        "last_sync": "46 分钟前",
        "records": "318,902",
        "latency_ms": 0,
        "health": 0,
        "desc": "供应商 / 采购 / 物流数据",
        "config": {"host": "10.0.5.7", "db": "scm_prod", "user": "aios_ro"},
    },
]

# ---------- 可选目录（添加数据源时选择） ----------

_CATALOG: List[Dict[str, Any]] = [
    {"type": "jdbc",  "name": "Oracle 数据库",  "icon": "🗄️", "tone": "blue",   "category": "数据库",     "desc": "通过 JDBC 接入关系型业务库"},
    {"type": "mysql", "name": "MySQL 数据库",   "icon": "🐬", "tone": "cyan",   "category": "数据库",     "desc": "轻量业务库 / 报表库"},
    {"type": "api",   "name": "REST API",       "icon": "🔌", "tone": "violet", "category": "接口",       "desc": "对接外部系统开放接口"},
    {"type": "mqtt",  "name": "IoT / MQTT",     "icon": "📡", "tone": "sky",    "category": "物联网",     "desc": "设备实时流数据"},
    {"type": "vector","name": "向量知识库",     "icon": "📚", "tone": "amber",  "category": "知识系统",   "desc": "文档 / 制度 RAG 检索"},
    {"type": "file",  "name": "文件 / 对象存储", "icon": "📁", "tone": "emerald","category": "文件",       "desc": "CSV / Excel / 文档批量导入"},
    {"type": "kafka", "name": "Kafka 流",       "icon": "🌊", "tone": "rose",   "category": "消息流",     "desc": "事件流实时接入"},
    {"type": "sap",   "name": "SAP",            "icon": "🟦", "tone": "blue",   "category": "业务系统",   "desc": "ERP 巨头系统"},
]

_STATUS_STATE: Dict[str, str] = {
    "connected": "数据正常",
    "warning": "同步延迟偏高",
    "error": "连接异常",
    "disconnected": "未连接",
}


def list_sources() -> List[Dict[str, Any]]:
    return [dict(s) for s in _SOURCES]


def get_source(src_id: str) -> Optional[Dict[str, Any]]:
    for s in _SOURCES:
        if s["id"] == src_id:
            return dict(s)
    return None


def list_catalog() -> List[Dict[str, Any]]:
    return [dict(c) for c in _CATALOG]


def add_source(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """根据目录或自定义配置新增一个数据源。返回新建对象。"""
    src_id = (payload.get("id") or _slug(payload.get("name", "source"))).strip()
    if not src_id:
        return None
    # 不允许重复 id
    if any(s["id"] == src_id for s in _SOURCES):
        return None
    new_src = {
        "id": src_id,
        "name": payload.get("name", src_id),
        "icon": payload.get("icon", "🔧"),
        "tone": payload.get("tone", "gray"),
        "category": payload.get("category", "自定义"),
        "type": payload.get("type", "api"),
        "status": "disconnected",
        "state": "未连接",
        "last_sync": "—",
        "records": "0",
        "latency_ms": 0,
        "health": 0,
        "desc": payload.get("desc", "新增数据源"),
        "config": payload.get("config", {}),
    }
    _SOURCES.append(new_src)
    return dict(new_src)


def delete_source(src_id: str) -> bool:
    for i, s in enumerate(_SOURCES):
        if s["id"] == src_id:
            _SOURCES.pop(i)
            return True
    return False


def toggle_source(src_id: str) -> Optional[Dict[str, Any]]:
    """连接 / 断开切换。模拟一次健康检查：
    断开 -> disconnected；连接 -> connected（真实接入时替换为连通性探测）。"""
    for s in _SOURCES:
        if s["id"] == src_id:
            if s["status"] in ("disconnected", "error"):
                s["status"] = "connected"
                s["state"] = _STATUS_STATE["connected"]
                s["last_sync"] = "刚刚"
                s["health"] = 95
                s["latency_ms"] = 60
            else:
                s["status"] = "disconnected"
                s["state"] = _STATUS_STATE["disconnected"]
                s["last_sync"] = "—"
                s["health"] = 0
                s["latency_ms"] = 0
            return dict(s)
    return None


def overview_sources() -> List[Dict[str, Any]]:
    """给首页用的精简结构（含末尾的"添加数据源"占位卡）。"""
    out = []
    for s in _SOURCES:
        out.append({
            "id": s["id"],
            "name": s["name"],
            "icon": s["icon"],
            "tone": s["tone"],
            "status": s["status"],
            "state": s["state"],
        })
    out.append({
        "id": "__add__",
        "name": "添加数据源",
        "icon": "+",
        "tone": "gray",
        "status": "add",
        "state": "",
    })
    return out


def _slug(name: str) -> str:
    return "".join(ch for ch in name if ch.isalnum() or ch in "_-").lower() or "src"
