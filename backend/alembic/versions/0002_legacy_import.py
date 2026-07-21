"""Revision ID: 0002_legacy_import
Revises: 0001_initial
Create Date: 2026-07-21 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_legacy_import"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

legacy_import_run_status = postgresql.ENUM(
    "IN_PROGRESS",
    "SUCCESS",
    "FAILED",
    name="legacy_import_run_status",
    create_type=False,
)
legacy_import_disposition = postgresql.ENUM(
    "IMPORTED",
    "SKIPPED_MISSING_CATEGORY",
    "SKIPPED_DUPLICATE_TITLE",
    name="legacy_import_disposition",
    create_type=False,
)


def upgrade() -> None:
    legacy_import_run_status.create(op.get_bind(), checkfirst=True)
    legacy_import_disposition.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "legacy_import_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_filename", sa.String(length=500), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_total_count", sa.Integer(), nullable=False),
        sa.Column("imported_item_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("skipped_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            legacy_import_run_status,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_legacy_import_runs_source_sha256"),
        "legacy_import_runs",
        ["source_sha256"],
        unique=False,
    )
    op.create_index(
        op.f("ix_legacy_import_runs_user_id"),
        "legacy_import_runs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "uq_legacy_import_runs_user_sha_success",
        "legacy_import_runs",
        ["user_id", "source_sha256"],
        unique=True,
        postgresql_where=sa.text("status = 'SUCCESS'"),
    )

    op.create_table(
        "legacy_import_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("import_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("disposition", legacy_import_disposition, nullable=False),
        sa.ForeignKeyConstraint(["import_run_id"], ["legacy_import_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_legacy_import_items_import_run_id"),
        "legacy_import_items",
        ["import_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_legacy_import_items_item_id"),
        "legacy_import_items",
        ["item_id"],
        unique=False,
    )

    op.create_table(
        "legacy_import_collections",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("import_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_name", sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(["import_run_id"], ["legacy_import_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_legacy_import_collections_collection_id"),
        "legacy_import_collections",
        ["collection_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_legacy_import_collections_import_run_id"),
        "legacy_import_collections",
        ["import_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_legacy_import_collections_import_run_id"),
        table_name="legacy_import_collections",
    )
    op.drop_index(
        op.f("ix_legacy_import_collections_collection_id"),
        table_name="legacy_import_collections",
    )
    op.drop_table("legacy_import_collections")
    op.drop_index(op.f("ix_legacy_import_items_item_id"), table_name="legacy_import_items")
    op.drop_index(op.f("ix_legacy_import_items_import_run_id"), table_name="legacy_import_items")
    op.drop_table("legacy_import_items")
    op.drop_index("uq_legacy_import_runs_user_sha_success", table_name="legacy_import_runs")
    op.drop_index(op.f("ix_legacy_import_runs_user_id"), table_name="legacy_import_runs")
    op.drop_index(op.f("ix_legacy_import_runs_source_sha256"), table_name="legacy_import_runs")
    op.drop_table("legacy_import_runs")
    legacy_import_disposition.drop(op.get_bind(), checkfirst=True)
    legacy_import_run_status.drop(op.get_bind(), checkfirst=True)
