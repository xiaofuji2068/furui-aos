# -*- coding: utf-8 -*-
"""从模型 metadata 导出 4 张缺表的列定义（供 TASK-020 对齐迁移使用）。"""
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")

import app.models  # noqa: F401
import app.models_ai  # noqa: F401
import app.models_ontology  # noqa: F401
from app.db import Base

for tname in ["agent_stages", "data_datasets", "inspection_work_orders", "task_reviews"]:
    t = Base.metadata.tables[tname]
    print(f"\n# === {tname} ===")
    for c in t.columns:
        typ = c.type
        typ_str = repr(typ)
        nullable = c.nullable
        default = c.default
        server_default = c.server_default
        idx = c.index
        uniq = c.unique
        fk = list(c.foreign_keys)[0] if c.foreign_keys else None
        line = f"sa.Column({c.name!r}, {typ_str}, "
        parts = []
        if fk:
            parts.append(f"sa.ForeignKey({fk.target_fullname!r}, ondelete={fk.ondelete!r})")
        if nullable is False:
            parts.append("nullable=False")
        if default is not None:
            d = default.arg if hasattr(default, "arg") else default
            if isinstance(d, str):
                parts.append(f"server_default={d!r}")
            else:
                parts.append(f"server_default={str(d)!r}")
        if idx:
            parts.append("index=True")
        if uniq:
            parts.append("unique=True")
        if c.primary_key:
            parts.append("primary_key=True")
        line += ", ".join(parts) + "),"
        print(line)
