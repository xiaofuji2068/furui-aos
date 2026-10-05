# -*- coding: utf-8 -*-
"""修复 inspection_records INSERT 列数（显式列名，id 自增）。"""
P = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\data_gateway.py"
with open(P, "r", encoding="utf-8") as f:
    src = f.read()

old = '    conn.executemany("INSERT INTO inspection_records VALUES (?,?,?,?,?,?,?,?,?)", records)'
new = ('    conn.executemany(\n'
       '        "INSERT INTO inspection_records (station_id, inspector, inspect_date, radiation, "\n'
       '        "temperature, vibration, health_score, status) VALUES (?,?,?,?,?,?,?,?)", records)')
assert old in src, "records insert missing"
src = src.replace(old, new)
with open(P, "w", encoding="utf-8") as f:
    f.write(src)
print("FIX records columns OK")
