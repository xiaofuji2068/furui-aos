# -*- coding: utf-8 -*-
"""修复 data_gateway.py：补回 _SCHEMA 闭合引号 + _seed_inspection_data 缩进。"""
P = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\data_gateway.py"
with open(P, "r", encoding="utf-8") as f:
    src = f.read()

changed = []

# 1) _SCHEMA 闭合引号：在 inspection_records 建表后补 """ 
marker = "    status       TEXT    DEFAULT 'normal'    -- normal / warning / alarm\n);\n\n"
replacement = "    status       TEXT    DEFAULT 'normal'    -- normal / warning / alarm\n);\n\"\"\"\n\n"
if "status       TEXT    DEFAULT 'normal'    -- normal / warning / alarm\n);\n\"\"\"" not in src:
    assert src.count(marker) == 1, f"schema close marker count={src.count(marker)}"
    src = src.replace(marker, replacement)
    changed.append("schema_close_quote")

# 2) _seed_inspection_data 尾部缩进修复：找到 records 列表结尾的 executemany/commit 补 4 空格
old_tail = "\n]\nconn.executemany(\"INSERT INTO inspection_records VALUES (?,?,?,?,?,?,?,?,?)\", records)\nconn.commit()"
new_tail = "\n    ]\n    conn.executemany(\"INSERT INTO inspection_records VALUES (?,?,?,?,?,?,?,?,?)\", records)\n    conn.commit()"
if old_tail in src:
    src = src.replace(old_tail, new_tail)
    changed.append("seed_tail_indent")
else:
    print("WARN: seed tail pattern not found, check manually")

with open(P, "w", encoding="utf-8") as f:
    f.write(src)
print("FIX OK:", changed)
