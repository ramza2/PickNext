"""Add items.release_year and items.synopsis (TMDB-3).

Revision ID: 0006_add_item_year_synopsis
Revises: 0005_add_item_external_identity
Create Date: 2026-07-24 17:50:00.000000

Existing rows keep release_year and synopsis NULL. No backfill.

Note: revision id is kept ≤32 chars (alembic_version.version_num).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_add_item_year_synopsis"
down_revision: Union[str, None] = "0005_add_item_external_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "items",
        sa.Column("release_year", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_items_release_year_range",
        "items",
        "release_year IS NULL OR (release_year >= 1000 AND release_year <= 9999)",
    )
    op.add_column(
        "items",
        sa.Column("synopsis", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("items", "synopsis")
    op.drop_constraint(
        "ck_items_release_year_range",
        "items",
        type_="check",
    )
    op.drop_column("items", "release_year")
