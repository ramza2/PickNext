"""Isolated DB checks for migration 0006 (do not use real picknext DB)."""

from __future__ import annotations

import os
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError


def main() -> int:
    host = os.environ.get("POSTGRES_HOST", "picknext-tmdb3-iso")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "picknext_tmdb3")
    user = os.environ.get("POSTGRES_USER", "picknext")
    password = os.environ.get("POSTGRES_PASSWORD", "picknext")
    url = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"
    engine = create_engine(url)

    def schema_state() -> tuple[list[str], list[str]]:
        with engine.connect() as conn:
            cols = [
                row[0]
                for row in conn.execute(
                    text(
                        """
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name='items'
                          AND column_name IN ('release_year', 'synopsis')
                        ORDER BY column_name
                        """
                    )
                )
            ]
            cons = [
                row[0]
                for row in conn.execute(
                    text(
                        """
                        SELECT conname FROM pg_constraint
                        WHERE conname='ck_items_release_year_range'
                        """
                    )
                )
            ]
        return cols, cons

    print("after_upgrade", schema_state())

    with engine.begin() as conn:
        uid = conn.execute(text("SELECT id FROM users LIMIT 1")).scalar()
        if uid is None:
            uid = conn.execute(
                text(
                    """
                    INSERT INTO users (email, display_name, password_hash)
                    VALUES ('iso@picknext.local', 'Iso', 'hash')
                    RETURNING id
                    """
                )
            ).scalar()
        cid = conn.execute(text("SELECT id FROM categories LIMIT 1")).scalar()
        if cid is None:
            cid = conn.execute(
                text(
                    """
                    INSERT INTO categories (user_id, name, category_type, sort_order)
                    VALUES (:u, '영화', 'MEDIA', 0)
                    RETURNING id
                    """
                ),
                {"u": uid},
            ).scalar()

        item_id = conn.execute(
            text(
                """
                INSERT INTO items (user_id, category_id, title, status, rating)
                VALUES (:u, :c, 'legacy', 'PLANNED', 0.0)
                RETURNING id
                """
            ),
            {"u": uid, "c": cid},
        ).scalar()
        row = conn.execute(
            text("SELECT release_year, synopsis FROM items WHERE id=:i"),
            {"i": item_id},
        ).one()
        print("legacy_nulls", row.release_year, row.synopsis)
        assert row.release_year is None
        assert row.synopsis is None

        for year in (1000, 2026, 9999):
            conn.execute(
                text(
                    """
                    INSERT INTO items (user_id, category_id, title, status, rating, release_year)
                    VALUES (:u, :c, :t, 'PLANNED', 0.0, :y)
                    """
                ),
                {"u": uid, "c": cid, "t": f"y{year}", "y": year},
            )

        for year in (999, 10000):
            try:
                with conn.begin_nested():
                    conn.execute(
                        text(
                            """
                            INSERT INTO items
                              (user_id, category_id, title, status, rating, release_year)
                            VALUES (:u, :c, :t, 'PLANNED', 0.0, :y)
                            """
                        ),
                        {"u": uid, "c": cid, "t": f"bad{year}", "y": year},
                    )
                print("FAIL_allowed", year)
                return 1
            except IntegrityError:
                print("rejected", year)

        long_ko = "줄거리 " + ("가" * 2000)
        conn.execute(
            text(
                """
                INSERT INTO items (user_id, category_id, title, status, rating, synopsis)
                VALUES (:u, :c, 'syn', 'PLANNED', 0.0, :s)
                """
            ),
            {"u": uid, "c": cid, "s": long_ko},
        )
        stored = conn.execute(
            text("SELECT synopsis FROM items WHERE title='syn'")
        ).scalar()
        assert stored == long_ko
        print("synopsis_long_ok", len(stored))

        before_count = conn.execute(text("SELECT count(*) FROM items")).scalar()
        print("items_before_downgrade", before_count)

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.downgrade(cfg, "0005_add_item_external_identity")
    print("after_downgrade", schema_state())
    cols, cons = schema_state()
    assert cols == []
    assert cons == []

    command.upgrade(cfg, "head")
    print("after_reupgrade", schema_state())
    cols, cons = schema_state()
    assert cols == ["release_year", "synopsis"]
    assert cons == ["ck_items_release_year_range"]

    with engine.connect() as conn:
        after_count = conn.execute(text("SELECT count(*) FROM items")).scalar()
        print("items_after_reupgrade", after_count)
        nulls = conn.execute(
            text(
                """
                SELECT count(*) FROM items
                WHERE title='legacy' AND release_year IS NULL AND synopsis IS NULL
                """
            )
        ).scalar()
        print("legacy_still_null", nulls)
        assert nulls == 1

    print("MIGRATION_ISO_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
