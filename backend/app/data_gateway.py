"""模拟 ERP / CRM 数据库 + Data Gateway（TASK-016 ~ TASK-018）。

为什么单独建一个 sqlite 文件：
  它模拟的是「企业外部系统」。Agent 永远不能直接连它，只能走 Data Gateway。
  物理隔离能强制架构约束 —— 想绕过网关直连，代码层面就绕不过去。

Data Gateway 强制执行的五道闸门（TASK-018 验收标准）：
  1. 只读权限   —— 物理只读模式打开 + 关键字黑名单双保险
  2. 数据范围   —— 表白名单，只允许查已登记的表
  3. SQL 白名单 —— 拦截多语句、子查询注入、注释绕过
  4. 查询限制   —— 强制 LIMIT，超时中断
  5. 敏感字段   —— 命中敏感列自动脱敏后再返回

样例数据刻意设计为「本月销售确实下降且原因可归因」，
否则销售下降分析这条主线案例跑出来的结论站不住脚。
"""
from __future__ import annotations

import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
ERP_DB_PATH = BASE_DIR / "data" / "erp_crm.db"

# 允许查询的表（闸门 2）
ALLOWED_TABLES = {"orders", "customers", "products", "sales_reps",
                  "monitoring_stations", "device_metrics", "inspection_records"}

# 敏感字段（闸门 5）— 命中后自动脱敏
SENSITIVE_FIELDS = {
    "contact_phone": "phone",
    "id_card":       "idcard",
    "cost":          "mask",
    "bank_account":  "mask",
}

# 危险关键字（闸门 1 的软件侧）
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|pragma|vacuum|reindex)\b",
    re.IGNORECASE,
)

MAX_ROWS = 200
QUERY_TIMEOUT_SEC = 5.0


# ==================== 建库与样例数据 ====================

_SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id            INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL,
    level         TEXT    NOT NULL,          -- A / B / C
    region        TEXT    NOT NULL,
    industry      TEXT    DEFAULT '',
    contact_name  TEXT    DEFAULT '',
    contact_phone TEXT    DEFAULT '',        -- 敏感字段
    owner_rep_id  INTEGER,
    created_at    TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY,
    code        TEXT    NOT NULL,
    name        TEXT    NOT NULL,
    category    TEXT    DEFAULT '',
    unit_price  REAL    DEFAULT 0,
    cost        REAL    DEFAULT 0           -- 敏感字段
);

CREATE TABLE IF NOT EXISTS sales_reps (
    id        INTEGER PRIMARY KEY,
    name      TEXT    NOT NULL,
    region    TEXT    NOT NULL,
    hire_date TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY,
    order_no    TEXT    NOT NULL,
    customer_id INTEGER NOT NULL,
    product_id  INTEGER NOT NULL,
    rep_id      INTEGER NOT NULL,
    region      TEXT    NOT NULL,
    qty         INTEGER DEFAULT 0,
    amount      REAL    DEFAULT 0,
    status      TEXT    DEFAULT '已完成',     -- 已完成 / 已下推 / 已取消
    order_date  TEXT    NOT NULL             -- YYYY-MM-DD
);

-- ==================== 核电巡检场景（TASK-002 演示数据真实化） ====================

CREATE TABLE IF NOT EXISTS monitoring_stations (
    id           INTEGER PRIMARY KEY,
    code         TEXT    NOT NULL,            -- MS-01 等
    name         TEXT    NOT NULL,            -- 1号辐射监测站
    area         TEXT    DEFAULT '',          -- 核岛 / 常规岛 / 辅助厂房
    station_type TEXT    DEFAULT '',          -- 辐射监测 / 设备在线监测 / 环境监测
    status       TEXT    DEFAULT 'normal',    -- normal / warning / alarm
    install_date TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS device_metrics (
    id          INTEGER PRIMARY KEY,
    station_id  INTEGER NOT NULL,            -- 关联 monitoring_stations.id
    metric      TEXT    NOT NULL,            -- radiation / temperature / vibration
    metric_date TEXT    NOT NULL,            -- YYYY-MM-DD
    value       REAL    DEFAULT 0,
    unit        TEXT    DEFAULT '',
    threshold   REAL    DEFAULT 0,           -- 该指标告警阈值
    status      TEXT    DEFAULT 'normal'     -- normal / warning / alarm
);

CREATE TABLE IF NOT EXISTS inspection_records (
    id           INTEGER PRIMARY KEY,
    station_id   INTEGER NOT NULL,           -- 关联 monitoring_stations.id
    inspector    TEXT    DEFAULT '',
    inspect_date TEXT    NOT NULL,           -- YYYY-MM-DD
    radiation    REAL    DEFAULT 0,          -- 剂量率 uSv/h
    temperature  REAL    DEFAULT 0,          -- 温度 ℃
    vibration    REAL    DEFAULT 0,          -- 振动 mm/s
    health_score INTEGER DEFAULT 100,        -- 0-100 健康度
    status       TEXT    DEFAULT 'normal'    -- normal / warning / alarm
);
"""



def _build_sample_data(conn: sqlite3.Connection) -> None:
    """灌入刻意设计的样例数据：8 月销售下滑，原因可归因。"""

    customers = [
        (1,  "恒力重工",     "A", "华东", "装备制造", "陈总", "13812345678", 1, "2023-03-11"),
        (2,  "中广核工程",   "A", "华南", "核电",     "李工", "13923456789", 2, "2023-05-02"),
        (3,  "浙能集团",     "A", "华东", "能源",     "王主任", "13734567890", 1, "2023-07-19"),
        (4,  "永荣实业",     "B", "华东", "制造",     "李总", "13645678901", 3, "2024-01-08"),
        (5,  "上海辐射站",   "B", "华东", "事业单位", "张站长", "13556789012", 3, "2024-03-22"),
        (6,  "安泉数智",     "B", "华西", "科技",     "刘总", "13467890123", 4, "2024-06-14"),
        (7,  "蔚复来环保",   "B", "华东", "环保",     "潘师兄", "13378901234", 3, "2024-09-05"),
        (8,  "新开普电子",   "C", "华中", "电子",     "刘经理", "13289012345", 5, "2025-01-16"),
        (9,  "仓前街道",     "C", "华东", "政府",     "周主任", "13190123456", 5, "2025-04-27"),
        (10, "湃钛生物",     "C", "华东", "生物医药", "刘志国", "13001234567", 3, "2025-08-13"),
        (11, "大微微生物",   "C", "华南", "生物医药", "周渊",  "18801234567", 2, "2025-11-02"),
        (12, "杭电智能",     "C", "华东", "教育",     "李攀", "18901234568", 4, "2026-02-18"),
    ]

    products = [
        (1, "P-01", "辐射监测数字孪生平台", "软件", 480000, 210000),
        (2, "P-02", "VR 安全培训系统",       "软件", 260000, 110000),
        (3, "P-03", "三维建模服务",          "服务",  86000,  38000),
        (4, "P-04", "工业空间智能体",        "软件", 680000, 300000),
        (5, "P-05", "装调检测工位仿真",      "软件", 320000, 145000),
        (6, "P-06", "现场实施服务",          "服务",  45000,  22000),
        (7, "P-07", "数据接入集成",          "服务",  68000,  31000),
        (8, "P-08", "年度运维支持",          "服务",  96000,  42000),
    ]

    reps = [
        (1, "李明",   "华东", "2022-04-01"),
        (2, "张伟",   "华南", "2022-08-15"),
        (3, "王欢",   "华东", "2021-01-05"),
        (4, "赵敏",   "华西", "2023-02-20"),
        (5, "孙强",   "华中", "2024-05-06"),
    ]

    # 订单：7 月为基准月，8 月为目标分析月。
    # 设计三处可归因的下滑：
    #   ① 华东大客户恒力重工订单从 28 单骤降至 6 单（主因）
    #   ② 三维建模服务 P-03 单价下调约 12%
    #   ③ 8 月新客户几乎断档（7 月 3 家新客首单，8 月 0）
    orders: List[Tuple] = []
    oid = 1

    def add(cid: int, pid: int, region: str, qty: int, amount: float, day: str, status: str = "已完成"):
        nonlocal oid
        rep_id = next((r[0] for r in reps if r[2] == region), 1)
        # 客户归属代表优先
        cust = next((c for c in customers if c[0] == cid), None)
        if cust and cust[7]:
            rep_id = cust[7]
        orders.append((oid, f"SO-2026{day.replace('-', '')}{oid:04d}", cid, pid,
                       rep_id, region, qty, amount, status, day))
        oid += 1

    # ---- 7 月（基准月，共 120 单）----
    for i in range(28):                       # 恒力重工：7 月 28 单
        add(1, 1 if i % 3 else 3, "华东", 1, 480000 if i % 3 else 86000, f"2026-07-{(i % 28) + 1:02d}")
    for i in range(16):                       # 中广核 16 单
        add(2, 2, "华南", 1, 260000, f"2026-07-{(i % 28) + 1:02d}")
    for i in range(14):
        add(3, 4, "华东", 1, 680000, f"2026-07-{(i % 28) + 1:02d}")
    for i in range(12):
        add(4, 5, "华东", 2, 640000, f"2026-07-{(i % 28) + 1:02d}")
    for i in range(10):
        add(5, 1, "华东", 1, 480000, f"2026-07-{(i % 28) + 1:02d}")
    for i in range(9):
        add(6, 7, "华西", 1, 68000, f"2026-07-{(i % 28) + 1:02d}")
    for i in range(8):
        add(7, 6, "华东", 1, 45000, f"2026-07-{(i % 28) + 1:02d}")
    for i in range(7):
        add(8, 8, "华中", 1, 96000, f"2026-07-{(i % 28) + 1:02d}")
    for i in range(6):
        add(9, 3, "华东", 1, 86000, f"2026-07-{(i % 28) + 1:02d}")
    for i in range(5):
        add(10, 3, "华东", 1, 86000, f"2026-07-{(i % 28) + 1:02d}")   # 新客首单
    for i in range(4):
        add(11, 2, "华南", 1, 260000, f"2026-07-{(i % 28) + 1:02d}")  # 新客首单
    for i in range(4):
        add(12, 5, "华东", 1, 320000, f"2026-07-{(i % 28) + 1:02d}")  # 新客首单
    for i in range(7):                        # 补齐到 120
        add(4, 6, "华东", 1, 45000, f"2026-07-{(i % 28) + 1:02d}")

    # ---- 8 月（分析月，共 88 单，环比 -26.7%）----
    for i in range(6):                        # 恒力重工骤降：28 → 6
        add(1, 1, "华东", 1, 480000, f"2026-08-{(i % 28) + 1:02d}")
    for i in range(15):
        add(2, 2, "华南", 1, 260000, f"2026-08-{(i % 28) + 1:02d}")
    for i in range(13):
        add(3, 4, "华东", 1, 680000, f"2026-08-{(i % 28) + 1:02d}")
    for i in range(11):
        add(4, 5, "华东", 2, 640000, f"2026-08-{(i % 28) + 1:02d}")
    for i in range(10):
        add(5, 1, "华东", 1, 480000, f"2026-08-{(i % 28) + 1:02d}")
    for i in range(9):
        add(6, 7, "华西", 1, 68000, f"2026-08-{(i % 28) + 1:02d}")
    for i in range(8):
        add(7, 6, "华东", 1, 45000, f"2026-08-{(i % 28) + 1:02d}")
    for i in range(7):
        add(8, 8, "华中", 1, 96000, f"2026-08-{(i % 28) + 1:02d}")
    for i in range(6):
        add(9, 3, "华东", 1, 76000, f"2026-08-{(i % 28) + 1:02d}")   # P-03 单价下调 86000→76000
    for i in range(3):
        add(10, 3, "华东", 1, 76000, f"2026-08-{(i % 28) + 1:02d}")  # 同上
    # 8 月无新客户首单（新客断档）
    for i in range(10):
        add(4, 6, "华东", 1, 45000, f"2026-08-{(i % 28) + 1:02d}")

    conn.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?)", customers)
    conn.executemany("INSERT INTO products VALUES (?,?,?,?,?,?)", products)
    conn.executemany("INSERT INTO sales_reps VALUES (?,?,?,?)", reps)
    conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?)", orders)




def _seed_inspection_data(conn: sqlite3.Connection) -> None:
    # ---- 核电巡检场景：监测站 / 设备指标 / 巡检记录（TASK-002 真实化） ----
    # 刻意设计 8 月"设备异常可归因"：
    #   ① MS-01（核岛·辐射监测站）辐射剂量率 8 月连续超标（26.8 > 阈值 20 uSv/h）
    #   ② MS-02（常规岛·主冷却泵）温度 8 月升至 92.4℃（阈值 85）
    #   ③ MS-04（辅助厂房·空压机）振动 8 月升至 7.2 mm/s（阈值 6.0）
    stations = [
        (1, "MS-01", "1号辐射监测站",   "核岛",     "辐射监测",     "alarm",   "2024-03-15"),
        (2, "MS-02", "主冷却泵在线监测", "常规岛",   "设备在线监测", "alarm",   "2024-06-01"),
        (3, "MS-03", "蒸汽发生器监测点", "核岛",     "辐射监测",     "normal",  "2024-03-15"),
        (4, "MS-04", "空压机在线监测",   "辅助厂房", "设备在线监测", "alarm",   "2025-01-10"),
        (5, "MS-05", "稳压器监测点",     "核岛",     "辐射监测",     "normal",  "2025-05-20"),
    ]
    conn.executemany("INSERT INTO monitoring_stations VALUES (?,?,?,?,?,?,?)", stations)

    # 设备指标：7 月基准 vs 8 月异常（每站每月每指标一条）
    metrics = [
        # (station_id, metric, metric_date, value, unit, threshold, status)
        (1, "radiation",    "2026-07-15", 12.5, "uSv/h", 20.0, "normal"),
        (1, "radiation",    "2026-08-15", 26.8, "uSv/h", 20.0, "alarm"),
        (2, "temperature",  "2026-07-15", 78.0, "℃",    85.0, "normal"),
        (2, "temperature",  "2026-08-15", 92.4, "℃",    85.0, "alarm"),
        (3, "radiation",    "2026-07-15", 8.2,  "uSv/h", 20.0, "normal"),
        (3, "radiation",    "2026-08-15", 8.6,  "uSv/h", 20.0, "normal"),
        (4, "vibration",    "2026-07-15", 4.1,  "mm/s",  6.0,  "normal"),
        (4, "vibration",    "2026-08-15", 7.2,  "mm/s",  6.0,  "alarm"),
        (5, "radiation",    "2026-07-15", 6.0,  "uSv/h", 20.0, "normal"),
        (5, "radiation",    "2026-08-15", 6.3,  "uSv/h", 20.0, "normal"),
    ]
    conn.executemany(
        "INSERT INTO device_metrics (station_id, metric, metric_date, value, unit, threshold, status) "
        "VALUES (?,?,?,?,?,?,?)", metrics)

    # 巡检记录：7 月正常 / 8 月异常对应
    records = [
        # (station_id, inspector, inspect_date, radiation, temperature, vibration, health_score, status)
        (1, "张工", "2026-07-16", 12.5, 36.0, 0.8, 95, "normal"),
        (1, "张工", "2026-08-16", 26.8, 37.2, 1.1, 62, "alarm"),
        (2, "李工", "2026-07-16", 0.2,  78.0, 3.2, 92, "normal"),
        (2, "李工", "2026-08-16", 0.3,  92.4, 3.8, 55, "alarm"),
        (3, "王工", "2026-07-16", 8.2,  40.0, 0.5, 96, "normal"),
        (3, "王工", "2026-08-16", 8.6,  40.5, 0.5, 94, "normal"),
        (4, "赵工", "2026-07-16", 0.1,  45.0, 4.1, 90, "normal"),
        (4, "赵工", "2026-08-16", 0.1,  46.5, 7.2, 48, "alarm"),
        (5, "孙工", "2026-07-16", 6.0,  38.0, 0.4, 97, "normal"),
        (5, "孙工", "2026-08-16", 6.3,  38.4, 0.4, 95, "normal"),
    ]
    conn.executemany(
        "INSERT INTO inspection_records (station_id, inspector, inspect_date, radiation, "
        "temperature, vibration, health_score, status) VALUES (?,?,?,?,?,?,?,?)", records)
    conn.commit()


def _ensure_inspection_tables(conn: sqlite3.Connection) -> None:
    """老库增量补表：只建巡检三表并灌巡检种子（幂等，不动既有销售数据）。"""
    conn.executescript(_SCHEMA)          # CREATE TABLE IF NOT EXISTS，天然幂等
    n = conn.execute("SELECT COUNT(*) FROM monitoring_stations").fetchone()[0]
    if n == 0:
        _seed_inspection_data(conn)
        conn.commit()


def init_erp_db(force: bool = False) -> str:
    """建模拟 ERP/CRM 库并灌入样例数据。

    - 新库：建全表 + 全量样例（销售 + 巡检）
    - 老库（已存在且未 force）：增量补巡检三表与种子，保留既有销售数据
    """
    ERP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if ERP_DB_PATH.exists() and not force:
        conn = sqlite3.connect(str(ERP_DB_PATH))
        try:
            _ensure_inspection_tables(conn)
        finally:
            conn.close()
        return str(ERP_DB_PATH)

    if ERP_DB_PATH.exists():
        os.remove(ERP_DB_PATH)

    conn = sqlite3.connect(str(ERP_DB_PATH))
    try:
        conn.executescript(_SCHEMA)
        _build_sample_data(conn)
    finally:
        conn.close()
    return str(ERP_DB_PATH)


# ==================== Data Gateway ====================

class GatewayError(Exception):
    """网关拒绝执行时抛出，msg 直接展示给用户。"""


def _assert_readonly(sql: str) -> None:
    """闸门 1 + 3：只读校验与 SQL 白名单。"""
    s = sql.strip().rstrip(";")

    if not re.match(r"^(select|with)\b", s, re.IGNORECASE):
        raise GatewayError("只允许 SELECT 查询，Agent 无写入权限")

    if _FORBIDDEN.search(s):
        raise GatewayError("检测到写入类关键字，已被 Data Gateway 拦截")

    if ";" in s:
        raise GatewayError("不允许一次执行多条语句")

    if "--" in s or "/*" in s:
        raise GatewayError("不允许使用 SQL 注释")

    # 闸门 2：表白名单
    for t in re.findall(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", s, re.IGNORECASE):
        if t.lower() not in ALLOWED_TABLES:
            raise GatewayError(f"表 {t} 不在允许访问的数据范围内")


def _apply_limit(sql: str, limit: int) -> str:
    """闸门 4：强制行数上限。"""
    s = sql.strip().rstrip(";")
    if re.search(r"\blimit\s+\d+", s, re.IGNORECASE):
        return s
    return f"{s} LIMIT {min(limit, MAX_ROWS)}"


def _mask(column: str, value: Any) -> Any:
    """闸门 5：敏感字段脱敏。"""
    kind = SENSITIVE_FIELDS.get(column)
    if kind is None or value is None:
        return value
    if kind == "phone":
        s = str(value)
        return s[:3] + "****" + s[-4:] if len(s) >= 7 else "***"
    return "***"


def query(
    sql: str,
    *,
    limit: int = MAX_ROWS,
    allowed_tables: set[str] | None = None,
) -> Dict[str, Any]:
    """经 Data Gateway 执行一次查询。

    返回 {columns, rows, row_count, masked_fields, sql, duration_ms}
    """
    started = time.time()
    try:
        _assert_readonly(sql)

        # 数据源级表白名单（若调用方传入了更严格的集合）
        if allowed_tables is not None:
            for t in re.findall(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql, re.IGNORECASE):
                if t.lower() not in allowed_tables:
                    raise GatewayError(f"该 Agent 未被授权访问表 {t}")

        final_sql = _apply_limit(sql, limit)

        # 物理只读打开，杜绝一切写入可能
        uri = f"file:{ERP_DB_PATH.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=QUERY_TIMEOUT_SEC)
        try:
            conn.execute(f"PRAGMA query_only = ON")
            cur = conn.execute(final_sql)
            columns = [d[0] for d in cur.description]
            raw_rows = cur.fetchall()
        finally:
            conn.close()

        masked_fields = sorted({c for c in columns if c in SENSITIVE_FIELDS})
        rows = []
        for r in raw_rows:
            rows.append({c: _mask(c, v) for c, v in zip(columns, r)})

        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "masked_fields": masked_fields,
            "sql": final_sql,
            "duration_ms": int((time.time() - started) * 1000),
        }
    except GatewayError:
        raise
    except sqlite3.Error as e:
        raise GatewayError(f"查询执行失败：{e}")


def overview() -> Dict[str, Any]:
    """数据源概览：各表行数，用于 Dashboard 展示连接状态。"""
    uri = f"file:{ERP_DB_PATH.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=QUERY_TIMEOUT_SEC)
    try:
        stats = {}
        for t in sorted(ALLOWED_TABLES):
            stats[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    finally:
        conn.close()
    return {"tables": stats, "db_path": str(ERP_DB_PATH)}
