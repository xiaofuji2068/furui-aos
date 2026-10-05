"""created_at server defaults (all tables)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-15 12:45:00

为全部 created_at 列补 server_default=CURRENT_TIMESTAMP，与模型层 default=_utcnow 对齐：
原生 SQL 插入（RLS 测试 / 企业数据导入）不再因 created_at 为 NULL 违反非空约束。
（列清单来自 2026-09-15 对 public schema 的 information_schema 实查：26 张表。）
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = [
    "action_receipts", "agent_executions", "agent_tasks", "agents",
    "ai_applications", "approval_rules", "approvals", "audit_logs",
    "business_scenarios", "companies", "data_connections", "data_sources",
    "departments", "eval_contracts", "knowledge_bases", "knowledge_documents",
    "notifications", "ontology_graph_snapshots", "ontology_objects",
    "ontology_outbox", "ontology_schema_revisions", "ontology_types",
    "sales_tasks", "tool_executions", "tools", "users",
]


def upgrade() -> None:
    for t in TABLES:
        op.alter_column(t, "created_at", server_default=text("CURRENT_TIMESTAMP"))


def downgrade() -> None:
    for t in TABLES:
        op.alter_column(t, "created_at", server_default=None)
