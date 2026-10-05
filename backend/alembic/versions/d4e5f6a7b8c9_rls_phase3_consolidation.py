# -*- coding: utf-8 -*-
"""Phase 3 收口：补齐缺失表 + 全库 RLS 幂等收口（60-02）

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-23 14:00:00

背景：agent_stages / data_datasets / inspection_work_orders / task_reviews
四张表仅存在于 SQLite create_all 形态（或测试库 create_all 补建），迁移链缺失；
且全库 RLS 只在部分表（sales_tasks / secret_entries 等）沉淀。本迁移：
1. 补齐 4 张缺失表（列定义与 ORM 模型一致，server_default 对齐语义；表已存在则跳过）；
2. 对全部有 company_id 的业务表幂等启用 RLS/FORCE + tenant_isolation policy
   （直列过滤）；
3. 对无 company_id 的业务子表（agent_skills/agent_steps/agent_stages）
   以父表复合租户键建立 EXISTS 子查询 policy；
4. 系统表（companies/permissions/role_permissions/user_roles/ontology_types
   /alembic_version）不启用 RLS（元数据/系统级，非租户数据）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 直列过滤（有 company_id 的业务表）
DIRECT_RLS_TABLES = [
    "action_receipts", "agent_executions", "agent_tasks", "agents",
    "ai_applications", "approval_rules", "approvals", "audit_logs",
    "business_scenarios", "data_connections", "data_datasets", "data_sources",
    "departments", "eval_contracts", "inspection_work_orders", "knowledge_bases",
    "knowledge_chunks", "knowledge_documents", "notifications",
    "ontology_graph_snapshots", "ontology_links", "ontology_objects",
    "ontology_outbox", "ontology_schema_revisions", "roles", "sales_tasks",
    "secret_entries", "task_reviews", "tool_executions", "tools", "users",
]

# 复合租户键子表（无 company_id，经父表归属）
SUBQUERY_RLS = {
    "agent_skills": ("agents", "agent_id"),
    "agent_steps": ("agent_tasks", "task_id"),
    "agent_stages": ("agent_tasks", "task_id"),
}


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _direct_policy(table: str) -> list[str]:
    cond = "company_id = NULLIF(current_setting('app.company_id', true), '')::int"
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;",
        f"DROP POLICY IF EXISTS tenant_isolation ON {table};",
        f"CREATE POLICY tenant_isolation ON {table} USING ({cond}) WITH CHECK ({cond});",
    ]


def _subquery_policy(table: str, parent: str, fk_col: str) -> list[str]:
    cond = (
        f"EXISTS (SELECT 1 FROM {parent} p WHERE p.id = {table}.{fk_col} "
        "AND p.company_id = NULLIF(current_setting('app.company_id', true), '')::int)"
    )
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;",
        f"DROP POLICY IF EXISTS tenant_isolation ON {table};",
        f"CREATE POLICY tenant_isolation ON {table} USING ({cond}) WITH CHECK ({cond});",
    ]


def upgrade() -> None:
    """Upgrade schema."""
    # ---- 1) 补齐 4 张缺失表（列与 ORM 模型一致；已存在则跳过，保证幂等） ----
    if not _table_exists('agent_stages'):
        op.create_table(
            'agent_stages',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('task_id', sa.Integer(), sa.ForeignKey('agent_tasks.id', ondelete='CASCADE'), nullable=False),
            sa.Column('seq', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('name', sa.String(80), nullable=False, server_default=''),
            sa.Column('kind', sa.String(20), nullable=False, server_default='data'),
            sa.Column('step_seqs', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('status', sa.String(20), nullable=False, server_default='Pending'),
            sa.Column('checkpoint', sa.Text(), nullable=False, server_default='{}'),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('finished_at', sa.DateTime(), nullable=True),
        )
    if not _table_exists('data_datasets'):
        op.create_table(
            'data_datasets',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('company_id', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('source_id', sa.String(64), nullable=False),
            sa.Column('name', sa.String(120), nullable=False),
            sa.Column('kind', sa.String(20), nullable=False, server_default='table'),
            sa.Column('entity', sa.String(120), nullable=False, server_default=''),
            sa.Column('row_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('version', sa.String(32), nullable=False, server_default='v1'),
            sa.Column('schema_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('lineage_json', sa.Text(), nullable=False, server_default='{}'),
            sa.Column('health_status', sa.String(16), nullable=False, server_default='healthy'),
            sa.Column('last_sync_at', sa.DateTime(), nullable=True),
            sa.Column('status', sa.String(16), nullable=False, server_default='active'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        )
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        if not sa.inspect(bind).has_index('data_datasets', 'ix_data_datasets_company_id'):
            op.create_index('ix_data_datasets_company_id', 'data_datasets', ['company_id'])
        if not sa.inspect(bind).has_index('data_datasets', 'ix_data_datasets_source_id'):
            op.create_index('ix_data_datasets_source_id', 'data_datasets', ['source_id'])
    if not _table_exists('inspection_work_orders'):
        op.create_table(
            'inspection_work_orders',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('station_code', sa.String(32), nullable=False, server_default=''),
            sa.Column('station_name', sa.String(120), nullable=False, server_default=''),
            sa.Column('title', sa.String(200), nullable=False, server_default=''),
            sa.Column('detail', sa.Text(), nullable=False, server_default=''),
            sa.Column('priority', sa.String(20), nullable=False, server_default='high'),
            sa.Column('owner', sa.String(64), nullable=False, server_default=''),
            sa.Column('due_date', sa.String(20), nullable=False, server_default=''),
            sa.Column('status', sa.String(20), nullable=False, server_default='待处置'),
            sa.Column('source', sa.String(20), nullable=False, server_default='agent'),
            sa.Column('agent_id', sa.Integer(), nullable=True),
            sa.Column('approval_id', sa.Integer(), nullable=True),
            sa.Column('created_by', sa.String(64), nullable=False, server_default=''),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        )
    if not _table_exists('task_reviews'):
        op.create_table(
            'task_reviews',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('task_id', sa.Integer(), sa.ForeignKey('agent_tasks.id', ondelete='CASCADE'), nullable=False),
            sa.Column('stage_id', sa.Integer(), sa.ForeignKey('agent_stages.id', ondelete='SET NULL'), nullable=True),
            sa.Column('reviewer_id', sa.Integer(), nullable=True),
            sa.Column('reviewer_name', sa.String(80), nullable=False, server_default=''),
            sa.Column('decision', sa.String(20), nullable=False, server_default='approve'),
            sa.Column('comment', sa.Text(), nullable=False, server_default=''),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        )

    # ---- 2) 全库 RLS 幂等收口（仅 PG） ----
    if bind.dialect.name == 'postgresql':
        for t in DIRECT_RLS_TABLES:
            for stmt in _direct_policy(t):
                op.execute(stmt)
        for t, (parent, fk) in SUBQUERY_RLS.items():
            for stmt in _subquery_policy(t, parent, fk):
                op.execute(stmt)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        for t in list(SUBQUERY_RLS) + DIRECT_RLS_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {t};")
            op.execute(f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;")
    if _table_exists('task_reviews'):
        op.drop_table('task_reviews')
    if _table_exists('inspection_work_orders'):
        op.drop_table('inspection_work_orders')
    if _table_exists('data_datasets'):
        op.drop_index('ix_data_datasets_company_id', table_name='data_datasets')
        op.drop_index('ix_data_datasets_source_id', table_name='data_datasets')
        op.drop_table('data_datasets')
    if _table_exists('agent_stages'):
        op.drop_table('agent_stages')
