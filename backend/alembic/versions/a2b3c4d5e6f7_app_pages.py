# -*- coding: utf-8 -*-
"""TASK-015：app_pages（低代码页面定义）+ RLS

Revision ID: a2b3c4d5e6f7
Revises: f6a7b8c9d0e1
Create Date: 2026-09-25 04:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table('app_pages'):
        op.create_table(
            'app_pages',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('company_id', sa.Integer(),
                      sa.ForeignKey('companies.id', ondelete='CASCADE'),
                      nullable=False, server_default='1'),
            sa.Column('code', sa.String(64), nullable=False),
            sa.Column('title', sa.String(128), nullable=False),
            sa.Column('description', sa.String(500), nullable=False, server_default=''),
            sa.Column('status', sa.String(16), nullable=False, server_default='draft'),
            sa.Column('version', sa.String(32), nullable=False, server_default='1.0'),
            sa.Column('layout_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.UniqueConstraint('company_id', 'code', name='uq_app_pages_company_code'),
        )
    if bind.dialect.name == 'postgresql':
        cond = "company_id = NULLIF(current_setting('app.company_id', true), '')::int"
        op.execute("ALTER TABLE app_pages ENABLE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE app_pages FORCE ROW LEVEL SECURITY;")
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON app_pages;")
        op.execute(f"CREATE POLICY tenant_isolation ON app_pages USING ({cond}) WITH CHECK ({cond});")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON app_pages;")
        op.execute("ALTER TABLE app_pages DISABLE ROW LEVEL SECURITY;")
    if sa.inspect(bind).has_table('app_pages'):
        op.drop_table('app_pages')
