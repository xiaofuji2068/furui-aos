# -*- coding: utf-8 -*-
"""修复 _seed_inspection_data 函数体缩进（整体重写该函数）。"""
P = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\data_gateway.py"
with open(P, "r", encoding="utf-8") as f:
    src = f.read()

start_marker = "def _seed_inspection_data(conn: sqlite3.Connection) -> None:\n"
end_marker = "def _ensure_inspection_tables(conn: sqlite3.Connection) -> None:"

i0 = src.index(start_marker)
i1 = src.index(end_marker)
assert i0 < i1

new_fn = '''def _seed_inspection_data(conn: sqlite3.Connection) -> None:
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
    conn.commit()


'''
src = src[:i0] + new_fn + src[i1:]

with open(P, "w", encoding="utf-8") as f:
    f.write(src)
print("FIX indent OK")
