# -*- coding: utf-8 -*-
"""bootstrap._seed_datasources 幂等分支：刷新已有数据源的 allowed_tables（旧库升级遗留空列表）。"""
from pathlib import Path
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\bootstrap.py")
t = p.read_text(encoding="utf-8")
old = '''    if ds_map:
        existing = [d.id for d in ds_map.values()]
        # 逐条补齐新增数据源（如 TASK-002 IoT 设备监测系统）'''
new = '''    if ds_map:
        existing = [d.id for d in ds_map.values()]
        # 幂等补齐：刷新已有数据源的 allowed_tables（旧库升级可能遗留空列表/旧定义）
        _EXPECT = {
            "ERP 销售系统": ["orders", "products", "sales_reps", "customers"],
            "CRM 客户系统": ["customers"],
            "IoT 设备监测系统": ["monitoring_stations", "device_metrics", "inspection_records"],
        }
        for _name, _tabs in _EXPECT.items():
            _ds = ds_map.get(_name)
            if _ds:
                try:
                    _cur = set(json.loads(_ds.allowed_tables or "[]"))
                except Exception:
                    _cur = set()
                if _cur != set(_tabs):
                    _ds.allowed_tables = json.dumps(_tabs, ensure_ascii=False)
        # 逐条补齐新增数据源（如 TASK-002 IoT 设备监测系统）'''
if old in t:
    t = t.replace(old, new, 1)
    p.write_text(t, encoding="utf-8")
    print("bootstrap.py: PATCHED")
else:
    print("bootstrap.py: MISS")