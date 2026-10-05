# -*- coding: utf-8 -*-
"""TASK-017：releases / release_changes（80-01 Apollo 交付发布，RLS 豁免）
+ edge_sites（70-03 Hub-Spoke 边缘站点，严格 RLS/FORCE）。

Revision ID: 9d1f4c7b2e8a
Revises: 8c9d0e1f2a3b
Create Date: 2026-10-05 10:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '9d1f4c7b2e8a'
down_revision: Union[str, Sequence[str], None] = '8c9d0e1f2a3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cond = "company_id = NULLIF(current_setting('app.company_id', true), '')::int"

    # 1) releases：系统级交付物目录（跨租户共享，RLS 豁免 —— 同 asset_bundles/permissions 先例）
    if not sa.inspect(bind).has_table('releases'):
        op.create_table(
            'releases',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('version', sa.String(32), nullable=False),
            sa.Column('channel', sa.String(16), nullable=False, server_default='draft'),
            sa.Column('status', sa.String(16), nullable=False, server_default='draft'),
            sa.Column('sbom_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('signature', sa.String(64), nullable=False, server_default=''),
            sa.Column('manifest_json', sa.Text(), nullable=False, server_default='{}'),
            sa.Column('notes', sa.Text(), nullable=False, server_default=''),
            sa.Column('promoted_to', sa.String(32), nullable=False, server_default=''),
            sa.Column('released_by_company_id', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.UniqueConstraint('version', name='uq_releases_version'),
        )

    # 2) release_changes：Release 逐条变更单（交付审计要能按 kind 过滤/计数）
    if not sa.inspect(bind).has_table('release_changes'):
        op.create_table(
            'release_changes',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('release_id', sa.Integer(), nullable=False),
            sa.Column('kind', sa.String(16), nullable=False, server_default='feat'),
            sa.Column('summary', sa.Text(), nullable=False, server_default=''),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.UniqueConstraint('release_id', 'kind', 'summary', name='uq_release_change'),
        )

    # 3) edge_sites：租户所有的边缘站点（严格 RLS/FORCE）
    if not sa.inspect(bind).has_table('edge_sites'):
        op.create_table(
            'edge_sites',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('site_code', sa.String(64), nullable=False),
            sa.Column('name', sa.String(128), nullable=False, server_default=''),
            sa.Column('site_type', sa.String(24), nullable=False, server_default='edge'),
            sa.Column('endpoint', sa.String(255), nullable=False, server_default=''),
            sa.Column('company_id', sa.Integer(),
                      sa.ForeignKey('companies.id', ondelete='CASCADE'),
                      nullable=False, server_default='1'),
            sa.Column('release_id', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('status', sa.String(16), nullable=False, server_default='registered'),
            sa.Column('site_token_hash', sa.String(64), nullable=False, server_default=''),
            sa.Column('version', sa.String(32), nullable=False, server_default=''),
            sa.Column('last_heartbeat_at', sa.DateTime(), nullable=True),
            sa.Column('metadata_json', sa.Text(), nullable=False, server_default='{}'),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.UniqueConstraint('site_code', name='uq_edge_sites_code'),
        )

    if bind.dialect.name == 'postgresql':
        op.execute("ALTER TABLE edge_sites ENABLE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE edge_sites FORCE ROW LEVEL SECURITY;")
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON edge_sites;")
        op.execute(f"CREATE POLICY tenant_isolation ON edge_sites USING ({cond}) WITH CHECK ({cond});")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON edge_sites;")
        op.execute("ALTER TABLE edge_sites DISABLE ROW LEVEL SECURITY;")
    if sa.inspect(bind).has_table('edge_sites'):
        op.drop_table('edge_sites')
    if sa.inspect(bind).has_table('release_changes'):
        op.drop_table('release_changes')
    if sa.inspect(bind).has_table('releases'):
        op.drop_table('releases')
