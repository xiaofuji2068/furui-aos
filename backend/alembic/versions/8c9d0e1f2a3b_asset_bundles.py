# -*- coding: utf-8 -*-
"""TASK-016：asset_bundles（系统资产目录，RLS 豁免）+ asset_installations（租户派生安装，RLS）

Revision ID: 8c9d0e1f2a3b
Revises: a2b3c4d5e6f7
Create Date: 2026-09-27 12:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '8c9d0e1f2a3b'
down_revision: Union[str, Sequence[str], None] = 'b7c8d9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # 1) asset_bundles：系统级资产目录（跨租户只读共享，RLS 豁免——同 permissions/ontology_types 先例）
    if not sa.inspect(bind).has_table('asset_bundles'):
        op.create_table(
            'asset_bundles',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('code', sa.String(64), nullable=False),
            sa.Column('name', sa.String(128), nullable=False),
            sa.Column('description', sa.String(500), nullable=False, server_default=''),
            sa.Column('version', sa.String(32), nullable=False, server_default='1.0'),
            sa.Column('kind', sa.String(24), nullable=False, server_default='bundle'),
            sa.Column('manifest_json', sa.Text(), nullable=False, server_default='{}'),
            sa.Column('content_json', sa.Text(), nullable=False, server_default='{}'),
            sa.Column('status', sa.String(16), nullable=False, server_default='draft'),
            sa.Column('created_by_company_id', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.UniqueConstraint('code', name='uq_asset_bundles_code'),
        )
    # 2) asset_installations：租户派生安装记录（严格 RLS/FORCE）
    if not sa.inspect(bind).has_table('asset_installations'):
        op.create_table(
            'asset_installations',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('company_id', sa.Integer(),
                      sa.ForeignKey('companies.id', ondelete='CASCADE'),
                      nullable=False, server_default='1'),
            sa.Column('bundle_id', sa.Integer(),
                      sa.ForeignKey('asset_bundles.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('bundle_code', sa.String(64), nullable=False, server_default=''),
            sa.Column('bundle_version', sa.String(32), nullable=False, server_default='1.0'),
            sa.Column('status', sa.String(16), nullable=False, server_default='installed'),
            sa.Column('derived_pages_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('derived_graphs_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('installed_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.UniqueConstraint('company_id', 'bundle_id',
                                name='uq_asset_install_company_bundle'),
        )
    if bind.dialect.name == 'postgresql':
        cond = "company_id = NULLIF(current_setting('app.company_id', true), '')::int"
        op.execute("ALTER TABLE asset_installations ENABLE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE asset_installations FORCE ROW LEVEL SECURITY;")
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON asset_installations;")
        op.execute(f"CREATE POLICY tenant_isolation ON asset_installations USING ({cond}) WITH CHECK ({cond});")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON asset_installations;")
        op.execute("ALTER TABLE asset_installations DISABLE ROW LEVEL SECURITY;")
    if sa.inspect(bind).has_table('asset_installations'):
        op.drop_table('asset_installations')
    if sa.inspect(bind).has_table('asset_bundles'):
        op.drop_table('asset_bundles')
