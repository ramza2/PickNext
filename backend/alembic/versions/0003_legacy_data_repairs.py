"""Expand items.title to TEXT for long legacy titles.

Revision ID: 0003_legacy_data_repairs
Revises: 0002_legacy_import
Create Date: 2026-07-21 14:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_legacy_data_repairs"
down_revision: Union[str, None] = "0002_legacy_import"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "items",
        "title",
        existing_type=sa.String(length=300),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "items",
        "title",
        existing_type=sa.Text(),
        type_=sa.String(length=300),
        existing_nullable=False,
    )
