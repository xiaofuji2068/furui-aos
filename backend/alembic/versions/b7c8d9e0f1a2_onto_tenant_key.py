"""ontology 唯一约束补复合租户键（TASK-015 回归暴露）

Revision ID: b7c8d9e0f1a2
Revises: a2b3c4d5e6f8
Create Date: 2026-09-26

uq_onto_obj / uq_onto_link 原先不含 company_id，
多企业下 (Customer,CUS-001) 会在企业间撞唯一键。
"""
from alembic import op

revision = "b7c8d9e0f1a2"
down_revision = "a2b3c4d5e6f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_onto_obj", "ontology_objects", type_="unique")
    op.create_unique_constraint(
        "uq_onto_obj", "ontology_objects",
        ["company_id", "type", "object_id"],
    )
    op.drop_constraint("uq_onto_link", "ontology_links", type_="unique")
    op.create_unique_constraint(
        "uq_onto_link", "ontology_links",
        ["company_id", "type", "source_id", "target_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_onto_obj", "ontology_objects", type_="unique")
    op.create_unique_constraint(
        "uq_onto_obj", "ontology_objects",
        ["type", "object_id"],
    )
    op.drop_constraint("uq_onto_link", "ontology_links", type_="unique")
    op.create_unique_constraint(
        "uq_onto_link", "ontology_links",
        ["type", "source_id", "target_id"],
    )
