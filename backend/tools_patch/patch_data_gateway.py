# -*- coding: utf-8 -*-
"""TASK-002 数据层补丁 v2（幂等）：data_gateway.py 增加核电巡检三表。"""
import os

P = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\data_gateway.py"
with open(P, "r", encoding="utf-8") as f:
    src = f.read()

changed = []

# ---------- 1. 表白名单（两种形态都兼容） ----------
new_allow = ('ALLOWED_TABLES = {"orders", "customers", "products", "sales_reps",\n'
             '                  "monitoring_stations", "device_metrics", "inspection_records"}')
if "monitoring_stations" not in src:
    for old in ('ALLOWED_TABLES = {"orders", "customers", "products", "sales_reps"}\n',
                'ALLOWED_TABLES = {"orders", "customers", "products", "sales_reps"}'):
        if old in src:
            src = src.replace(old, new_allow)
            changed.append("allow_list")
            break
    else:
        raise AssertionError("allow list pattern missing")

# ---------- 2. schema 追加三表 ----------
anchor = "    order_date  TEXT    NOT NULL             -- YYYY-MM-DD\n);\n\"\"\""
new_tables = """    order_date  TEXT    NOT NULL             -- YYYY-MM-DD
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
if "monitoring_stations (" not in src:
    assert anchor in src, "schema anchor missing"
    src = src.replace(anchor, new_tables)
    changed.append("schema")

# ---------- 3. 样例数据尾部追加巡检数据 ----------
old_tail = '    conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?)", orders)\n    conn.commit()'
inspection_seed = '''    conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?)", orders)

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
    conn.executemany("INSERT INTO device_metrics VALUES (?,?,?,?,?,?,?,?)", metrics)

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
    conn.executemany("INSERT INTO inspection_records VALUES (?,?,?,?,?,?,?,?,?)", records)
    conn.commit()'''
if "inspection_records VALUES" not in src:
    assert old_tail in src, "sample tail anchor missing"
    src = src.replace(old_tail, inspection_seed)
    changed.append("sample_data")

with open(P, "w", encoding="utf-8") as f:
    f.write(src)
print("PATCH OK:", changed)
