"""最小真实连接器（图谱 10-02 数据源与连接器）。

设计落点（见 docs/最小真实连接器设计.md）：
- 不改动销售主线 / 分析 / 只读网关。连接器只负责在「同步」时把真实数据
  **物化（materialize）**进 erp_crm.db（外部系统的缓存投影）。
- 下游 data_gateway.query() 的只读闸门 + PII 脱敏在真实数据上照样生效，天然安全。

目前只实现 REST JSON 一种连接器，验证「接真实源」这条路通；JDBC / MQTT / SAP 等留作后续。
"""
from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List

import httpx

from .data_gateway import ERP_DB_PATH, _SCHEMA

# 连接器可物化的实体 <-> 目标表 + 允许写入的列（防止 JSON 注入未知列）
_ENTITY_TABLES: Dict[str, Dict[str, str]] = {
    "customers": {
        "id": "id", "name": "name", "level": "level", "region": "region",
        "industry": "industry", "contact_name": "contact_name",
        "contact_phone": "contact_phone", "owner_rep_id": "owner_rep_id",
        "created_at": "created_at",
    },
    "products": {
        "id": "id", "code": "code", "name": "name", "category": "category",
        "unit_price": "unit_price", "cost": "cost",
    },
    "sales_reps": {
        "id": "id", "name": "name", "region": "region", "hire_date": "hire_date",
    },
    "orders": {
        "id": "id", "order_no": "order_no", "customer_id": "customer_id",
        "product_id": "product_id", "rep_id": "rep_id", "region": "region",
        "qty": "qty", "amount": "amount", "status": "status",
        "order_date": "order_date",
    },
}

_CONNECTOR_TYPES = {"rest", "file"}


class DataConnector(ABC):
    """连接器抽象：pull() 返回归一化记录 {entity: [ {column: value, ...}, ... ]}。"""

    name: str = "abstract"

    @abstractmethod
    def pull(self) -> Dict[str, List[dict]]:
        raise NotImplementedError


class RestJsonConnector(DataConnector):
    """REST JSON 连接器：GET/POST 一个端点，按 mapping 把 JSON 映射成表行。

    config 结构：
      endpoint:    str   必填，HTTP(S) URL
      method:      str   GET(默认) / POST
      headers:     dict  额外请求头
      auth:        dict  {"type": "bearer"|"apikey", "env": "ERP_API_KEY"}
                          （生产应从环境变量取密钥；dev 态也允许内联 {"token": "..."}）
      mapping:     dict  每个实体的字段映射 {entity: {json_field: column}}
                          缺省时直接用列名当 JSON 字段名
      timeout_sec: int   默认 10
      retries:     int   网络错误 / 超时 / 5xx 的重试次数（默认 2）
      backoff_sec: float 指数退避基数（默认 0.5，第 n 次等待 0.5*2^n 秒）
                          注：4xx（含 401/403 鉴权错）属请求/鉴权问题，不重试，立即上报
    """

    name = "rest"

    def __init__(self, config: Dict[str, Any]):
        self.cfg = config or {}
        self.endpoint = self.cfg.get("endpoint", "")
        if not self.endpoint:
            raise ValueError("RestJsonConnector 需要 config.endpoint")
        self.method = (self.cfg.get("method") or "GET").upper()
        self.headers = dict(self.cfg.get("headers") or {})
        self.mapping = self.cfg.get("mapping") or {}
        self.timeout = int(self.cfg.get("timeout_sec") or 10)
        self.retries = int(self.cfg.get("retries") or 2)
        self.backoff = float(self.cfg.get("backoff_sec") or 0.5)
        self._apply_auth()

    def _apply_auth(self) -> None:
        auth = self.cfg.get("auth") or {}
        atype = (auth.get("type") or "").lower()
        if atype in ("bearer", "apikey"):
            token = os.environ.get(auth.get("env", ""), "") or auth.get("token", "")
            if token:
                if atype == "bearer":
                    self.headers["Authorization"] = f"Bearer {token}"
                else:
                    self.headers[auth.get("header", "X-API-Key")] = token

    def pull(self) -> Dict[str, List[dict]]:
        """拉取并归一化真实数据。

        重试策略（应对外网 ERP 抖动）：
          - 网络错误 / 超时 / 5xx：指数退避重试（retries 次，backoff_sec 翻倍）；
          - 4xx（含 401/403 鉴权错）：不重试，立即上报 —— 重试无意义且会刷屏。
        """
        payload: Any = None
        for attempt in range(1 + self.retries):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    if self.method == "POST":
                        resp = client.post(self.endpoint, headers=self.headers or None)
                    else:
                        resp = client.get(self.endpoint, headers=self.headers or None)
                if resp.status_code >= 500:
                    # 服务端瞬时错误，值得重试
                    if attempt < self.retries:
                        time.sleep(self.backoff * (2 ** attempt))
                        continue
                    raise RuntimeError(f"ERP 持续返回 5xx：{resp.status_code}")
                resp.raise_for_status()  # 4xx（鉴权 / 请求错）不重试，直接抛
                payload = resp.json()
                break
            except (httpx.TransportError, httpx.TimeoutException) as e:
                # 网络抖动 / 连接超时：退避后重试
                if attempt < self.retries:
                    time.sleep(self.backoff * (2 ** attempt))
                    continue
                raise
        if payload is None:
            raise RuntimeError("ERP 拉取未返回任何数据（重试耗尽）")

        raw: Dict[str, List[dict]] = {}
        # 归一化：支持 {entity: [...]}、顶层数组（默认当 orders）、或 {"data": {entity: [...]}}
        if isinstance(payload, list):
            raw["orders"] = payload
        elif isinstance(payload, dict):
            for k, v in payload.items():
                if k in _ENTITY_TABLES and isinstance(v, list):
                    raw[k] = v
            nested = payload.get("data")
            if isinstance(nested, dict):
                for k, v in nested.items():
                    if k in _ENTITY_TABLES and isinstance(v, list):
                        raw.setdefault(k, v)
        return _normalize(raw, self.mapping)


def _coerce(value: Any) -> Any:
    """CSV 全是字符串：按目标语义轻量转换。数字转 int/float，其余保持字符串。"""
    if not isinstance(value, str):
        return value
    s = value.strip()
    if s == "":
        return None
    s2 = s.replace(",", "")  # 容错千分位
    if re.fullmatch(r"-?\d+", s2):
        return int(s2)
    try:
        return float(s2)
    except ValueError:
        return s


def _normalize(raw: Dict[str, List[dict]], mapping: Dict[str, Dict[str, str]]) -> Dict[str, List[dict]]:
    """把 {entity: [原始行]} 按 mapping 归一化成表行（两种连接器共用）。

    - mapping 缺省时列名等于 JSON/CSV 字段名；
    - 仅允许写入 _ENTITY_TABLES 登记的列（防注入未知列）；
    - 主键缺失的行丢弃，避免污染。
    """
    out: Dict[str, List[dict]] = {}
    for entity, rows in raw.items():
        if entity not in _ENTITY_TABLES:
            continue
        colmap = mapping.get(entity, {c: c for c in _ENTITY_TABLES[entity]})
        norm = []
        for r in rows:
            row = {}
            for json_field, column in colmap.items():
                if column in _ENTITY_TABLES[entity] and json_field in r:
                    row[column] = _coerce(r[json_field])
            if row.get("id") is None:
                continue  # 主键缺失的行丢弃，避免污染
            if row:
                norm.append(row)
        if norm:
            out[entity] = norm
    return out


class CsvFileConnector(DataConnector):
    """文件 / CSV 连接器：读取 base_dir 下的实体 CSV，按 mapping 归一化。

    设计落点同 REST：只负责「同步」时把真实数据物化进 erp_crm.db，
    下游只读网关 / 脱敏 / 分析 / 建单全部原样复用。

    config 结构：
      base_dir:  str   必填，CSV 所在目录
      files:     dict  实体名 -> 文件名（缺省 <entity>.csv，即 customers.csv 等）
      mapping:   dict  同 REST（CSV 表头字段 -> 表列）；缺省列名=表头
      encoding:  str   文件编码（默认 utf-8-sig，兼容带 BOM 的 Excel 导出）
    """

    name = "file"

    def __init__(self, config: Dict[str, Any]):
        self.cfg = config or {}
        self.base_dir = (self.cfg.get("base_dir") or "").strip()
        if not self.base_dir:
            raise ValueError("CsvFileConnector 需要 config.base_dir")
        self.files = self.cfg.get("files") or {}
        self.mapping = self.cfg.get("mapping") or {}
        self.encoding = self.cfg.get("encoding") or "utf-8-sig"

    def pull(self) -> Dict[str, List[dict]]:
        raw: Dict[str, List[dict]] = {}
        for entity in _ENTITY_TABLES:
            fname = self.files.get(entity) or f"{entity}.csv"
            path = os.path.join(self.base_dir, fname)
            if not os.path.exists(path):
                continue
            with open(path, newline="", encoding=self.encoding) as f:
                reader = csv.DictReader(f)
                rows = [dict(r) for r in reader]
            if rows:
                raw[entity] = rows
        return _normalize(raw, self.mapping)


def build_connector(source_type: str, config: Dict[str, Any]) -> DataConnector:
    if source_type == "rest":
        return RestJsonConnector(config)
    if source_type == "file":
        return CsvFileConnector(config)
    raise ValueError(f"不支持的连接器类型：{source_type}")


def materialize(records: Dict[str, List[dict]]) -> Dict[str, int]:
    """把归一化记录写入 erp_crm.db（幂等全量覆盖四张销售表）。复用既有表结构。"""
    ERP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    existed = ERP_DB_PATH.exists()
    conn = sqlite3.connect(str(ERP_DB_PATH))
    try:
        if not existed:
            conn.executescript(_SCHEMA)
        counts: Dict[str, int] = {}
        for entity, colmap in _ENTITY_TABLES.items():
            rows = records.get(entity, [])
            if not rows:
                continue
            cols = list(colmap.values())
            col_sql = ",".join(cols)
            placeholders = ",".join("?" for _ in cols)
            conn.execute(f"DELETE FROM {entity}")
            conn.executemany(
                f"INSERT INTO {entity} ({col_sql}) VALUES ({placeholders})",
                [[r.get(c) for c in cols] for r in rows],
            )
            counts[entity] = len(rows)
        conn.commit()
        return counts
    finally:
        conn.close()


def sync_source(src_id: str, source: Dict[str, Any]) -> Dict[str, Any]:
    """对一个数据源配置执行真实同步：pull -> materialize -> 返回状态。

    source 是 store_data_sources 里的一条记录（含 type / config / status）。
    失败时返回 error 且不破坏既有数据。
    """
    started = time.time()
    try:
        stype = source.get("type", "")
        if stype not in _CONNECTOR_TYPES:
            return {"ok": False, "src_id": src_id, "status": "error", "records": 0,
                    "latency_ms": 0, "health": 0,
                    "error": f"类型 {stype} 暂不支持真实同步（仅支持 {sorted(_CONNECTOR_TYPES)}）"}
        connector = build_connector(stype, source.get("config", {}))
        records = connector.pull()
        counts = materialize(records)
        total = sum(counts.values())
        return {
            "ok": True, "src_id": src_id, "status": "connected",
            "records": total, "counts": counts,
            "latency_ms": int((time.time() - started) * 1000),
            "health": 98, "error": None,
        }
    except Exception as e:  # noqa: BLE001 — 同步失败不能炸启动流程
        return {
            "ok": False, "src_id": src_id, "status": "error",
            "records": 0, "latency_ms": int((time.time() - started) * 1000),
            "health": 0, "error": str(e),
        }
