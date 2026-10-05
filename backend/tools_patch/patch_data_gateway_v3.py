# -*- coding: utf-8 -*-
"""TASK-002 数据层补丁 v3：init_erp_db 支持老库增量补巡检表（幂等）。"""
import os

P = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\data_gateway.py"
with open(P, "r", encoding="utf-8") as f:
    src = f.read()

# 1) 把 _build_sample_data 里的巡检种子段抽成独立函数 _seed_inspection_data
seed_start = "    # ---- 核电巡检场景：监测站 / 设备指标 / 巡检记录（TASK-002 真实化） ----"
seed_end = "    conn.executemany(\"INSERT INTO inspection_records VALUES (?,?,?,?,?,?,?,?,?)\", records)\n    conn.commit()"
assert seed_start in src, "seed start missing"
assert seed_end in src, "seed end missing"
i0 = src.index(seed_start)
i1 = src.index(seed_end) + len(seed_end)
seed_block = src[i0:i1]

# 缩进层级：seed_block 在 _build_sample_data 内部（4 空格缩进），抽成模块级函数需改为 0/4 空格
def _dedent(block: str, n: int = 4) -> str:
    lines = []
    for ln in block.split("\n"):
        if ln.startswith(" " * n):
            lines.append(ln[n:])
        else:
            lines.append(ln)
    return "\n".join(lines)

fn_seed = "def _seed_inspection_data(conn: sqlite3.Connection) -> None:\n" + _dedent(seed_block)

# 2) 新的 init_erp_db：老库存在时增量补巡检表 + 种子（幂等）
old_init = '''def init_erp_db(force: bool = False) -> str:
    """建模拟 ERP/CRM 库并灌入样例数据。已存在且未 force 则跳过。"""
    ERP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if ERP_DB_PATH.exists() and not force:
        return str(ERP_DB_PATH)

    if ERP_DB_PATH.exists():
        os.remove(ERP_DB_PATH)

    conn = sqlite3.connect(str(ERP_DB_PATH))
    try:
        conn.executescript(_SCHEMA)
        _build_sample_data(conn)
    finally:
        conn.close()
    return str(ERP_DB_PATH)'''

new_init = '''def _ensure_inspection_tables(conn: sqlite3.Connection) -> None:
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
    return str(ERP_DB_PATH)'''

assert old_init in src, "init function pattern missing"

# 3) 组装：先替换 init，再把种子函数插到 init 之前（即 old_init 位置处整体替换）
src = src.replace(seed_block, "")           # 从 _build_sample_data 中移除内联种子
src = src.replace(old_init, fn_seed + "\n\n\n" + new_init)

with open(P, "w", encoding="utf-8") as f:
    f.write(src)
print("PATCH v3 OK")
