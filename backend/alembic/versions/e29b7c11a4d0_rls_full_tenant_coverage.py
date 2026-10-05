"""rls full tenant coverage

Revision ID: e29b7c11a4d0
Revises: 371ad190fce1
Create Date: 2026-09-10 21:30:00

把 RLS/FORCE RLS 扩展到当前全部 27 张带 company_id 的租户表
（补全 action_receipts / eval_contracts / ontology_outbox /
 ontology_graph_snapshots 四张后建表，并对既有表幂等重建 policy）。

Policy 语义（图谱 60-02 行级隔离）：
  - USING + WITH CHECK 双写：读、写（含 INSERT 的 WITH CHECK）都按租户过滤
  - current_setting('app.company_id', true) 缺省返回 NULL（不报错）；
    NULLIF 把空串归 NULL；无租户上下文时（未登录/未注入）查不到任何租户行
  - FORCE RLS：连表 owner 也受约束，杜绝绕过
SQLite（开发）上自动跳过。
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e29b7c11a4d0'
down_revision: Union[str, Sequence[str], None] = '371ad190fce1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 当前全部带 company_id 的租户表（27 张，与 app.models*/app.models_ontology 对齐）
TENANT_TABLES = [
    "action_receipts", "agent_executions", "agent_tasks", "agents",
    "ai_applications", "approval_rules", "approvals", "audit_logs",
    "business_scenarios", "data_connections", "data_sources", "departments",
    "eval_contracts", "knowledge_bases", "knowledge_chunks",
    "knowledge_documents", "notifications", "ontology_graph_snapshots",
    "ontology_links", "ontology_objects", "ontology_outbox",
    "ontology_schema_revisions", "roles", "sales_tasks", "tool_executions",
    "tools", "users",
]

_RLS = """
ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {t} FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON {t};
CREATE POLICY tenant_isolation ON {t}
  USING (company_id = NULLIF(current_setting('app.company_id', true), '')::int)
  WITH CHECK (company_id = NULLIF(current_setting('app.company_id', true), '')::int);
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
