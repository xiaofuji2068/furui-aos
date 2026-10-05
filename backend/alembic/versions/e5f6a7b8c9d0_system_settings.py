# -*- coding: utf-8 -*-
"""TASK-021：system_settings 表（设置落库，替代内存暂存）+ RLS 收口

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-23 16:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table('system_settings'):
        op.create_table(
            'system_settings',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('company_id', sa.Integer(),
                      sa.ForeignKey('companies.id', ondelete='CASCADE'),
                      nullable=False, server_default='1'),
            sa.Column('key', sa.String(64), nullable=False),
            sa.Column('value', sa.Text(), nullable=False, server_default=''),
            sa.Column('updated_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.UniqueConstraint('company_id', 'key', name='uq_system_settings_company_key'),
        )
    if bind.dialect.name == 'postgresql':
        cond = "company_id = NULLIF(current_setting('app.company_id', true), '')::int"
        op.execute("ALTER TABLE system_settings ENABLE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE system_settings FORCE ROW LEVEL SECURITY;")
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON system_settings;")
        op.execute(f"CREATE POLICY tenant_isolation ON system_settings USING ({cond}) WITH CHECK ({cond});")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON system_settings;")
        op.execute("ALTER TABLE system_settings DISABLE ROW LEVEL SECURITY;")
    if sa.inspect(bind).has_table('system_settings'):
        op.drop_table('system_settings')
