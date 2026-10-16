# -*- coding: utf-8 -*-
"""TASK-018-2：Trace 链路 ID — 给 tool_executions / audit_logs 加 trace_id 列。

一次 HTTP 请求 = 一条 trace；入口中间件生成 trace_id（或透传 X-Trace-Id），
沿途审计日志（write_audit）与工具执行记录（tool_gateway._log）写入同一 trace_id，
运维可按 trace_id 把「同一请求触发的全部动作」串起来查。

Revision ID: a3b4c5d6e7f8
Revises: 9d1f4c7b2e8a
Create Date: 2026-10-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, Sequence[str], None] = '9d1f4c7b2e8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    from sqlalchemy import inspect as sa_inspect

    return column in {c["name"] for c in sa_inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if not _has_column("tool_executions", "trace_id"):
        op.add_column(
            "tool_executions",
            sa.Column("trace_id", sa.String(64), nullable=True),
        )
        op.create_index("ix_tool_executions_trace_id", "tool_executions", ["trace_id"])

    if not _has_column("audit_logs", "trace_id"):
        op.add_column(
            "audit_logs",
            sa.Column("trace_id", sa.String(64), nullable=True),
        )
        op.create_index("ix_audit_logs_trace_id", "audit_logs", ["trace_id"])


def downgrade() -> None:
    bind = op.get_bind()
    # SQLite 删除索引需带表名；PG 不带也可，统一带表名更稳。
    if bind.dialect.name != "sqlite":
        op.drop_index("ix_audit_logs_trace_id", table_name="audit_logs")
        op.drop_index("ix_tool_executions_trace_id", table_name="tool_executions")
    else:
        op.drop_index("ix_audit_logs_trace_id", table_name="audit_logs")
        op.drop_index("ix_tool_executions_trace_id", table_name="tool_executions")
    op.drop_column("audit_logs", "trace_id")
    op.drop_column("tool_executions", "trace_id")
