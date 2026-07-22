"""Schema checks for removing Item soft-delete (D-2)."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.models import Item


def test_items_table_has_no_deleted_at(engine: Engine) -> None:
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("items")}
    assert "deleted_at" not in columns

    index_names = {idx["name"] for idx in inspector.get_indexes("items")}
    assert "ix_items_active" not in index_names
    assert "ix_items_user_id_category_id" in index_names
    assert "ix_items_user_id_status" in index_names
    assert "ix_items_collection_id" in index_names


def test_item_model_metadata_matches_hard_delete_schema() -> None:
    assert "deleted_at" not in Item.__table__.c
    assert "deleted_at" not in Item.__mapper__.columns
    names = {index.name for index in Item.__table__.indexes}
    assert "ix_items_active" not in names
    assert "ix_items_user_id_category_id" in names


def test_recommendation_history_item_fk_still_restrict(engine: Engine) -> None:
    rows = (
        engine.connect()
        .execute(
            text(
                """
            SELECT confdeltype
            FROM pg_constraint
            WHERE conname = 'recommendation_history_items_item_id_fkey'
            """
            )
        )
        .all()
    )
    assert len(rows) == 1
    # 'r' = restrict in pg_constraint.confdeltype
    assert rows[0][0] == "r"


def test_recommendation_history_parent_fk_cascades_items(engine: Engine) -> None:
    rows = (
        engine.connect()
        .execute(
            text(
                """
            SELECT confdeltype
            FROM pg_constraint
            WHERE conname = 'recommendation_history_items_recommendation_history_id_fkey'
            """
            )
        )
        .all()
    )
    assert len(rows) == 1
    # 'c' = cascade
    assert rows[0][0] == "c"


def test_legacy_import_item_fk_cascades(engine: Engine) -> None:
    rows = (
        engine.connect()
        .execute(
            text(
                """
            SELECT confdeltype
            FROM pg_constraint
            WHERE conname = 'legacy_import_items_item_id_fkey'
            """
            )
        )
        .all()
    )
    assert len(rows) == 1
    assert rows[0][0] == "c"
