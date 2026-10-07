"""Widen items.progress_note from VARCHAR(200) to TEXT.

Revision ID: 0008_progress_note_text
Revises: 0007_add_auth_tables
Create Date: 2026-10-07 05:20:00.000000

Upgrade is non-destructive (VARCHAR → TEXT).

Downgrade is destructive: values longer than 200 characters are truncated
with LEFT(..., 200) before casting back to VARCHAR(200).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_progress_note_text"
down_revision: Union[str, None] = "0007_add_auth_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "items",
        "progress_note",
        existing_type=sa.String(length=200),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Destructive: long notes cannot fit VARCHAR(200).
    op.execute(
        """
        UPDATE items
        SET progress_note = LEFT(progress_note, 200)
        WHERE progress_note IS NOT NULL
          AND char_length(progress_note) > 200
        """
    )
    op.alter_column(
        "items",
        "progress_note",
        existing_type=sa.Text(),
        type_=sa.String(length=200),
        existing_nullable=True,
    )
