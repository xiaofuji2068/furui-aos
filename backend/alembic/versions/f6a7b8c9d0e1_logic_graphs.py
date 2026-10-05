# -*- coding: utf-8 -*-
"""TASK-014：logic_graphs / logic_nodes（Logic 决策编排图）+ RLS 收口

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-23 17:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table('logic_graphs'):
        op.create_table(
            'logic_graphs',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('company_id', sa.Integer(),
                      sa.ForeignKey('companies.id', ondelete='CASCADE'),
                      nullable=False, server_default='1'),
            sa.Column('code', sa.String(64), nullable=False),
            sa.Column('name', sa.String(128), nullable=False),
            sa.Column('version', sa.String(32), nullable=False, server_default='1.0'),
            sa.Column('description', sa.Text(), nullable=False, server_default=''),
            sa.Column('status', sa.String(16), nullable=False, server_default='draft'),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.UniqueConstraint('company_id', 'code', name='uq_logic_graphs_company_code'),
        )
    if not sa.inspect(bind).has_table('logic_nodes'):
        op.create_table(
            'logic_nodes',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('graph_id', sa.Integer(),
                      sa.ForeignKey('logic_graphs.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('company_id', sa.Integer(),
                      sa.ForeignKey('companies.id', ondelete='CASCADE'),
                      nullable=False, server_default='1'),
            sa.Column('seq', sa.Integer(), nullable=False),
            sa.Column('key', sa.String(64), nullable=False, server_default=''),
            sa.Column('title', sa.String(128), nullable=False),
            sa.Column('kind', sa.String(24), nullable=False),
            sa.Column('tool', sa.String(64), nullable=False, server_default=''),
            sa.Column('label', sa.String(255), nullable=False, server_default=''),
            sa.Column('params_json', sa.Text(), nullable=False, server_default='{}'),
            sa.Column('depends_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.UniqueConstraint('graph_id', 'seq', name='uq_logic_nodes_graph_seq'),
        )
        op.create_index('ix_logic_nodes_graph_id', 'logic_nodes', ['graph_id'])
    if sa.inspect(bind).has_table('logic_nodes'):
        op.execute("ALTER TABLE logic_nodes ADD COLUMN IF NOT EXISTS company_id INTEGER NOT NULL DEFAULT 1;")
        op.create_index('ix_logic_nodes_company_id', 'logic_nodes', ['company_id'], unique=False)
    if bind.dialect.name == 'postgresql':
        cond = "company_id = NULLIF(current_setting('app.company_id', true), '')::int"
        for tbl in ('logic_graphs', 'logic_nodes'):
            op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
            op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY;")
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {tbl};")
            op.execute(f"CREATE POLICY tenant_isolation ON {tbl} USING ({cond}) WITH CHECK ({cond});")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        for tbl in ('logic_graphs', 'logic_nodes'):
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {tbl};")
            op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY;")
    for tbl, idx in (('logic_nodes', 'ix_logic_nodes_graph_id'),):
        if sa.inspect(bind).has_table(tbl):
            if bind.dialect.name == 'postgresql':
                op.drop_index(idx, table_name=tbl)
            op.drop_table(tbl)
    if sa.inspect(bind).has_table('logic_graphs'):
        op.drop_table('logic_graphs')
