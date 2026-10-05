# -*- coding: utf-8 -*-
"""Chain-tail no-op migration (was a1b2c3d4e5f6 collision placeholder).

Revision ID: a2b3c4d5e6f8
Revises: a2b3c4d5e6f7
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'a2b3c4d5e6f8'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
