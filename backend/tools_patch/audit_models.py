# -*- coding: utf-8 -*-
"""TASK-020 探查：扫描所有 ORM 表的列清单（找无 company_id 的表）+ Python default 用法。"""
import io
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")

import app.models  # noqa: F401
import app.models_ai  # noqa: F401
import app.models_ontology  # noqa: F401
from app.db import Base

print("===== 1) 所有表与 company_id 列 =====")
for table in sorted(Base.metadata.tables.keys()):
    cols = [c.name for c in Base.metadata.tables[table].columns]
    has_cid = "company_id" in cols
    mark = "  <-- 无 company_id" if not has_cid else ""
    print(f"  {table:36s} cols={len(cols):3d}{mark}")

print("\n===== 2) Python default= 列（非 server_default，收口审计对象） =====")
for table_name in sorted(Base.metadata.tables.keys()):
    t = Base.metadata.tables[table_name]
    for c in t.columns:
        if c.default is not None and getattr(c.default, "is_scalar", False) and c.server_default is None:
            # 排除关系/主键自增
            if c.primary_key:
                continue
            print(f"  {table_name}.{c.name}: default={c.default.arg!r}")
