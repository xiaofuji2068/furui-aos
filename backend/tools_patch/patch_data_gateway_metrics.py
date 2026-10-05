# -*- coding: utf-8 -*-
"""修复 device_metrics INSERT 列数（显式列名，id 自增）。"""
P = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\data_gateway.py"
with open(P, "r", encoding="utf-8") as f:
    src = f.read()

old = '    conn.executemany("INSERT INTO device_metrics VALUES (?,?,?,?,?,?,?,?)", metrics)'
new = ('    conn.executemany(\n'
       '        "INSERT INTO device_metrics (station_id, metric, metric_date, value, unit, threshold, status) "\n'
       '        "VALUES (?,?,?,?,?,?,?)", metrics)')
assert old in src, "metrics insert missing"
src = src.replace(old, new)
with open(P, "w", encoding="utf-8") as f:
    f.write(src)
print("FIX metrics columns OK")
