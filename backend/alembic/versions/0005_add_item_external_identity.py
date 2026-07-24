"""Add external content identity fields to items (TMDB-1).

Revision ID: 0005_add_item_external_identity
Revises: 0004_remove_item_soft_delete
Create Date: 2026-07-24 13:30:00.000000

Existing Legacy rows keep all new columns NULL. No backfill.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_add_item_external_identity"
down_revision: Union[str, None] = "0004_remove_item_soft_delete"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "items",
        sa.Column("external_source", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "items",
        sa.Column("external_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "items",
        sa.Column("external_media_type", sa.String(length=16), nullable=True),
    )
    op.add_column("items", sa.Column("original_title", sa.Text(), nullable=True))
    op.add_column(
        "items",
        sa.Column("original_language", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "items",
        sa.Column("poster_path", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "items",
        sa.Column("backdrop_path", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "items",
        sa.Column(
            "external_metadata_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_check_constraint(
        "ck_items_external_identity_all_or_none",
        "items",
        """
        (
          external_source IS NULL
          AND external_id IS NULL
          AND external_media_type IS NULL
        )
        OR
        (
          external_source IS NOT NULL
          AND external_id IS NOT NULL
          AND external_media_type IS NOT NULL
        )
        """,
    )
    op.create_index(
        "uq_items_user_external_identity",
        "items",
        ["user_id", "external_source", "external_media_type", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_items_user_external_identity",
        table_name="items",
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.drop_constraint(
        "ck_items_external_identity_all_or_none",
        "items",
        type_="check",
    )
    op.drop_column("items", "external_metadata_updated_at")
    op.drop_column("items", "backdrop_path")
    op.drop_column("items", "poster_path")
    op.drop_column("items", "original_language")
    op.drop_column("items", "original_title")
    op.drop_column("items", "external_media_type")
    op.drop_column("items", "external_id")
    op.drop_column("items", "external_source")
