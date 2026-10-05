# -*- coding: utf-8 -*-
"""TASK-020 default 列收口审计：扫模型 metadata，输出
A) Python default 但无 server_default 的列（裸 SQL/批量导入会 NULL）
B) DB 层 NOT NULL 且无 server_default 的列（绕过 ORM 写入必炸）
落档 docs/TASK-020-default审计.md。
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ROOT = Path(__file__).resolve().parents[1]

import sqlalchemy as sa
from sqlalchemy import create_engine, MetaData, inspect

# 汇总所有模型表
from app import models, models_ai  # noqa: F401

md = MetaData()
for mod in (models, models_ai):
    for tbl in mod.Base.metadata.tables.values():
        if tbl.name not in md.tables:
            tbl.to_metadata(md)

rows_a = []   # python default 无 server_default
rows_b = []   # NOT NULL 无 server_default（DB 层裸写风险）
for tname, tbl in sorted(md.tables.items()):
    for col in tbl.columns:
        py_dflt = col.default is not None and not isinstance(col.default, sa.sql.elements.TextClause)
        has_sd = col.server_default is not None
        if py_dflt and not has_sd:
            rows_a.append((tname, col.name, str(col.type), "python-default", col.nullable))
        if not col.nullable and not has_sd and not col.primary_key and not col.foreign_keys:
            rows_b.append((tname, col.name, str(col.type), "not-null-no-sd", col.nullable))

def fmt(rows):
    return "\n".join(f"  {t}.{c}  {ty}  [{k}] nullable={n}" for t, c, ty, k, n in rows)

doc = f"""# TASK-020 default 列收口审计报告

生成时间：2026-09-23（对齐迁移 d4e5f6a7b8c9 之后）

## 结论摘要
- Python `default=` 但**无 server_default** 的列：{len(rows_a)} 处
  （ORM 写入生效；裸 SQL / 批量导入 / 非 ORM 通道不生效，可能落 NULL）
- **DB 层 NOT NULL 且无 server_default** 的列：{len(rows_b)} 处
  （绕过 ORM 的写入（如工具直连、数据回填、测试裸 SQL）会违反约束）

## A) Python default 无 server_default（{len(rows_a)}）
{fmt(rows_a) if rows_a else "  （无）"}

## B) NOT NULL 且无 server_default（{len(rows_b)}）
{fmt(rows_b) if rows_b else "  （无）"}

## 处置原则
- A 类：风险中，建议分批为高频写列补 server_default（或在迁移链中一次性对齐）；
- B 类：风险高，凡存在非 ORM 写入通道的表应优先补 server_default 或放宽 nullable；
- 本轮（TASK-020）已在迁移中为补齐的 4 张表全部列显式声明 server_default，
  与 ORM 语义对齐；其余按 BACKLOG 后续任务分批处理，避免单轮大改。
"""

out = ROOT.parent / "docs" / "TASK-020-default审计.md"
with io.open(out, "w", encoding="utf-8") as f:
    f.write(doc)
print(f"OK: {out}")
print(f"A类(py-default无server_default): {len(rows_a)}  B类(not-null无server_default): {len(rows_b)}")
for t, c, ty, k, n in rows_b[:30]:
    print(f"  B: {t}.{c}")
