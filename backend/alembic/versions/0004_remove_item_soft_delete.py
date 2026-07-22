"""Remove Item soft-delete column and partial active index.

Revision ID: 0004_remove_item_soft_delete
Revises: 0003_legacy_data_repairs
Create Date: 2026-07-22 15:00:00.000000

Schema downgrade can restore deleted_at and ix_items_active, but Hard Delete
data (Item rows, recommendation history, legacy mappings) cannot be restored.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_remove_item_soft_delete"
down_revision: Union[str, None] = "0003_legacy_data_repairs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    soft_deleted_count = connection.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM items
            WHERE deleted_at IS NOT NULL
            """
        )
    ).scalar_one()
    if soft_deleted_count > 0:
        raise RuntimeError(
            "Cannot remove items.deleted_at: "
            f"{soft_deleted_count} soft-deleted item(s) require manual review."
        )

    op.drop_index("ix_items_active", table_name="items")
    op.drop_column("items", "deleted_at")


def downgrade() -> None:
    # Schema-only restore. Hard-deleted rows are not recoverable.
    op.add_column(
        "items",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_items_active",
        "items",
        ["user_id", "category_id"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
