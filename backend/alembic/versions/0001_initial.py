"""Initial schema for PickNext domain models.

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-21 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

category_type = postgresql.ENUM(
    "MEDIA",
    "BOOK",
    "FOOD",
    "GENERAL",
    name="category_type",
    create_type=False,
)
item_status = postgresql.ENUM(
    "PLANNED",
    "COMPLETED",
    name="item_status",
    create_type=False,
)
status_filter = postgresql.ENUM(
    "PLANNED",
    "COMPLETED",
    "ALL",
    name="status_filter",
    create_type=False,
)


def upgrade() -> None:
    category_type.create(op.get_bind(), checkfirst=True)
    item_status.create(op.get_bind(), checkfirst=True)
    status_filter.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "categories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("category_type", category_type, nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_categories_user_id_name"),
    )
    op.create_index("ix_categories_user_id", "categories", ["user_id"], unique=False)

    op.create_table(
        "collections",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_collections_user_id_name"),
    )
    op.create_index("ix_collections_user_id", "collections", ["user_id"], unique=False)

    op.create_table(
        "items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("status", item_status, nullable=False),
        sa.Column("rating", sa.Numeric(precision=2, scale=1), nullable=False),
        sa.Column("progress_note", sa.String(length=200), nullable=True),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("rating >= 0 AND rating <= 5", name="ck_items_rating_range"),
        sa.CheckConstraint(
            "(rating * 2) = floor(rating * 2)",
            name="ck_items_rating_half_step",
        ),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_items_user_id", "items", ["user_id"], unique=False)
    op.create_index("ix_items_category_id", "items", ["category_id"], unique=False)
    op.create_index("ix_items_collection_id", "items", ["collection_id"], unique=False)
    op.create_index("ix_items_user_id_category_id", "items", ["user_id", "category_id"], unique=False)
    op.create_index("ix_items_user_id_status", "items", ["user_id", "status"], unique=False)
    op.create_index(
        "ix_items_active",
        "items",
        ["user_id", "category_id"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "recommendation_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status_filter", status_filter, nullable=False),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "selected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recommendation_history_user_id",
        "recommendation_history",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_recommendation_history_category_id",
        "recommendation_history",
        ["category_id"],
        unique=False,
    )
    op.create_index(
        "ix_recommendation_history_collection_id",
        "recommendation_history",
        ["collection_id"],
        unique=False,
    )

    op.create_table(
        "recommendation_history_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("recommendation_history_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title_snapshot", sa.String(length=300), nullable=False),
        sa.Column("status_at_selection", item_status, nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["recommendation_history_id"],
            ["recommendation_history.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "recommendation_history_id",
            "item_id",
            name="uq_recommendation_history_items_history_item",
        ),
    )
    op.create_index(
        "ix_recommendation_history_items_recommendation_history_id",
        "recommendation_history_items",
        ["recommendation_history_id"],
        unique=False,
    )
    op.create_index(
        "ix_recommendation_history_items_item_id",
        "recommendation_history_items",
        ["item_id"],
        unique=False,
    )
    op.create_index(
        "ix_recommendation_history_items_history_sort",
        "recommendation_history_items",
        ["recommendation_history_id", "sort_order"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recommendation_history_items_history_sort",
        table_name="recommendation_history_items",
    )
    op.drop_index(
        "ix_recommendation_history_items_item_id",
        table_name="recommendation_history_items",
    )
    op.drop_index(
        "ix_recommendation_history_items_recommendation_history_id",
        table_name="recommendation_history_items",
    )
    op.drop_table("recommendation_history_items")

    op.drop_index("ix_recommendation_history_collection_id", table_name="recommendation_history")
    op.drop_index("ix_recommendation_history_category_id", table_name="recommendation_history")
    op.drop_index("ix_recommendation_history_user_id", table_name="recommendation_history")
    op.drop_table("recommendation_history")

    op.drop_index("ix_items_active", table_name="items")
    op.drop_index("ix_items_user_id_status", table_name="items")
    op.drop_index("ix_items_user_id_category_id", table_name="items")
    op.drop_index("ix_items_collection_id", table_name="items")
    op.drop_index("ix_items_category_id", table_name="items")
    op.drop_index("ix_items_user_id", table_name="items")
    op.drop_table("items")

    op.drop_index("ix_collections_user_id", table_name="collections")
    op.drop_table("collections")

    op.drop_index("ix_categories_user_id", table_name="categories")
    op.drop_table("categories")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    status_filter.drop(op.get_bind(), checkfirst=True)
    item_status.drop(op.get_bind(), checkfirst=True)
    category_type.drop(op.get_bind(), checkfirst=True)
