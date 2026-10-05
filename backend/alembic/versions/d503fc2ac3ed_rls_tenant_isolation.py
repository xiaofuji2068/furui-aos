"""rls tenant isolation

Revision ID: d503fc2ac3ed
Revises: 742aa39332c4
Create Date: 2026-09-06 21:31:33.872135

对全部带 company_id 的业务表启用 PostgreSQL 行级安全（图谱 60-02 租户隔离）。
SQLite（开发）上自动跳过 —— 本迁移只在 PostgreSQL 生效。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd503fc2ac3ed'
down_revision: Union[str, Sequence[str], None] = '742aa39332c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 带 company_id 的全部业务表（含步骤 2.2 新增的本体 3 表）
TENANT_TABLES = [
    "audit_logs", "ai_applications", "approval_rules", "data_sources",
    "departments", "knowledge_bases", "roles", "sales_tasks", "tools",
    "agents", "business_scenarios", "data_connections", "knowledge_documents",
    "users", "agent_tasks", "knowledge_chunks", "notifications",
    "tool_executions", "agent_executions", "approvals",
    "ontology_objects", "ontology_links", "ontology_schema_revisions",
]

_RLS = """
ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {t} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {t}
  USING (company_id = current_setting('app.company_id')::int);
"""


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite 开发库：无 RLS，跳过（租户隔离由应用层 company_id 过滤承担）
        return
    for t in TENANT_TABLES:
        op.execute(_RLS.format(t=t))


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for t in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {t};")
        op.execute(f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;")
