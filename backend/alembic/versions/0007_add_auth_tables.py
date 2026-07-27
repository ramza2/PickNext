"""Add auth columns and session/verification tables (AUTH-1).

Revision ID: 0007_add_auth_tables
Revises: 0006_add_item_year_synopsis
Create Date: 2026-07-27 09:45:00.000000

Existing users keep login_id NULL. No password/login_id backfill.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_add_auth_tables"
down_revision: Union[str, None] = "0006_add_item_year_synopsis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("login_id", sa.String(length=30), nullable=True))
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_users_login_id_format",
        "users",
        "login_id IS NULL OR login_id ~ '^[a-z0-9][a-z0-9._-]{3,29}$'",
    )
    op.create_index(
        "uq_users_login_id",
        "users",
        ["login_id"],
        unique=True,
        postgresql_where=sa.text("login_id IS NOT NULL"),
    )

    op.create_table(
        "user_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "is_persistent",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])

    op.create_table(
        "auth_verification_codes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("login_id", sa.String(length=30), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "purpose IN ('SIGNUP', 'FIND_LOGIN_ID', 'RESET_PASSWORD')",
            name="ck_auth_verification_codes_purpose",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_verification_codes_purpose_email",
        "auth_verification_codes",
        ["purpose", "email"],
    )
    op.create_index(
        "ix_auth_verification_codes_purpose_login_id",
        "auth_verification_codes",
        ["purpose", "login_id"],
    )
    op.create_index(
        "ix_auth_verification_codes_expires_at",
        "auth_verification_codes",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auth_verification_codes_expires_at",
        table_name="auth_verification_codes",
    )
    op.drop_index(
        "ix_auth_verification_codes_purpose_login_id",
        table_name="auth_verification_codes",
    )
    op.drop_index(
        "ix_auth_verification_codes_purpose_email",
        table_name="auth_verification_codes",
    )
    op.drop_table("auth_verification_codes")

    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_index("ix_user_sessions_expires_at", table_name="user_sessions")
    op.drop_table("user_sessions")

    op.drop_index(
        "uq_users_login_id",
        table_name="users",
        postgresql_where=sa.text("login_id IS NOT NULL"),
    )
    op.drop_constraint("ck_users_login_id_format", "users", type_="check")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "login_id")
