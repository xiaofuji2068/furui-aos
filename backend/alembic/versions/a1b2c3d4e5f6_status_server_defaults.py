"""status server defaults (companies)

Revision ID: a1b2c3d4e5f6
Revises: e29b7c11a4d0
Create Date: 2026-09-15 12:30:00

修复 create_all 与迁移的不一致：模型层 Company.status 只有 Python default="active"，
迁移层列定义 NOT NULL 且无 server_default —— 原生 SQL 插入（如 RLS 测试、未来数据导入）
会因 status 为 NULL 违反非空约束。补 server_default 使数据库层自带默认值，两条路径一致。
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "e29b7c11a4d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("companies", "status", server_default="active")


def downgrade() -> None:
    op.alter_column("companies", "status", server_default=None)
