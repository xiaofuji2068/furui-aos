# -*- coding: utf-8 -*-
"""SecretRef / Keychain 密钥表（60-04）

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-23 12:00:00

新增 secret_entries 表（按租户隔离 + RLS/FORCE RLS），
承载 60-04 SecretRef/Keychain：密钥落库、PII/Retention/Region 标注、对外脱敏。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'secret_entries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ref_key', sa.String(120), nullable=False),
        sa.Column('kind', sa.String(30), nullable=False, server_default='custom'),
        sa.Column('secret_value', sa.Text(), nullable=False, server_default=''),
        sa.Column('pii_level', sa.String(20), nullable=False, server_default='none'),
        sa.Column('retention_days', sa.Integer(), nullable=False, server_default='365'),
        sa.Column('region', sa.String(20), nullable=False, server_default='cn'),
        sa.Column('note', sa.String(255), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('company_id', 'ref_key', name='uq_secret_entries_company_ref'),
    )

    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("""
        ALTER TABLE secret_entries ENABLE ROW LEVEL SECURITY;
        ALTER TABLE secret_entries FORCE ROW LEVEL SECURITY;
        CREATE POLICY tenant_isolation ON secret_entries
          USING (company_id = NULLIF(current_setting('app.company_id', true), '')::int)
          WITH CHECK (company_id = NULLIF(current_setting('app.company_id', true), '')::int);
        """)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON secret_entries;")
        op.execute("ALTER TABLE secret_entries DISABLE ROW LEVEL SECURITY;")
    op.drop_table('secret_entries')
