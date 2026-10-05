# -*- coding: utf-8 -*-
"""TASK-013：db.py ensure_column 跨方言（SQLite PRAGMA -> SQLAlchemy inspector）。"""
import io

p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\db.py"
with io.open(p, "r", encoding="utf-8") as f:
    src = f.read()

old = '''def ensure_column(db, table: str, column: str, ddl: str) -> bool:
    """幂等加列（SQLite 无原生 ALTER 迁移）：列缺失时 ALTER TABLE ADD COLUMN。

    返回是否执行了 ALTER。create_all 只建新表、不改已有表，
    因此对既有表的新增字段必须显式补齐（如 approvals.decision_lineage）。
    """
    cols = {r[1] for r in db.execute(text(f"PRAGMA table_info({table})")).fetchall()}
    if column in cols:
        return False
    db.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
    db.commit()
    return True'''

new = '''def ensure_column(db, table: str, column: str, ddl: str) -> bool:
    """幂等加列（跨方言 SQLite/PG）：列缺失时 ALTER TABLE ADD COLUMN。

    返回是否执行了 ALTER。create_all 只建新表、不改已有表，
    因此对既有表的新增字段必须显式补齐（如 approvals.decision_lineage）。
    """
    from sqlalchemy import inspect as sa_inspect

    insp = sa_inspect(db.get_bind())
    cols = {c["name"] for c in insp.get_columns(table)}
    if column in cols:
        return False
    db.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
    db.commit()
    return True'''

if old not in src:
    print("WARN: ensure_column anchor not found")
    raise SystemExit(1)
src = src.replace(old, new, 1)
with io.open(p, "w", encoding="utf-8") as f:
    f.write(src)
print("OK: ensure_column cross-dialect")
