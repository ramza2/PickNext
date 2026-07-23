#!/usr/bin/env python3
"""RC-2 bootstrap: seed-compatible user + QA fixtures on picknext_write_rc only.

Safety:
  - Refuses ``picknext`` / ``postgres``.
  - Requires explicit ``--postgres-db`` or ``POSTGRES_DB``.
  - Only ``picknext_write_rc`` / ``picknext_write_rc_*`` allowed.
  - Does not touch Seed volume, ``docker compose down -v``, or DROP DATABASE.

Run (after alembic upgrade head on the isolated DB)::

  docker compose cp backend/scripts/rc2_bootstrap_fixtures.py backend:/app/rc2_bootstrap_fixtures.py
  docker compose exec -e POSTGRES_DB=picknext_write_rc backend \\
    python rc2_bootstrap_fixtures.py --postgres-db picknext_write_rc
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys

FORBIDDEN_DB_NAMES = frozenset({"picknext", "postgres"})
ALLOWED_EXACT = frozenset({"picknext_write_rc"})
ALLOWED_PREFIX = "picknext_write_rc_"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap RC QA fixtures on isolated DB.")
    parser.add_argument("--postgres-db", metavar="NAME")
    parser.add_argument("--database-url", metavar="URL")
    parser.add_argument(
        "--reset-fixtures",
        action="store_true",
        help="Delete current user's RC-named collections/items/categories before recreate "
        "(does not drop the database).",
    )
    return parser.parse_args()


def configure_database(args: argparse.Namespace) -> None:
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    if args.postgres_db:
        os.environ["POSTGRES_DB"] = args.postgres_db
    if not args.database_url and not os.environ.get("POSTGRES_DB"):
        raise SystemExit(
            "RC bootstrap requires --postgres-db picknext_write_rc "
            "or POSTGRES_DB=picknext_write_rc."
        )


def assert_safe_database(settings) -> None:
    db_name = (settings.postgres_db or "").strip()
    if not db_name or db_name in FORBIDDEN_DB_NAMES:
        raise RuntimeError(
            f"RC bootstrap must run against an isolated database (refused {db_name!r})."
        )
    if db_name not in ALLOWED_EXACT and not db_name.startswith(ALLOWED_PREFIX):
        raise RuntimeError(
            f"RC bootstrap refused {db_name!r}; "
            f"allowed {sorted(ALLOWED_EXACT)!r} or {ALLOWED_PREFIX}*."
        )
    url_db = str(getattr(settings.sqlalchemy_database_url, "database", None) or "").strip()
    if url_db in FORBIDDEN_DB_NAMES or (
        url_db
        and url_db not in ALLOWED_EXACT
        and not url_db.startswith(ALLOWED_PREFIX)
    ):
        raise RuntimeError(
            f"RC bootstrap refused connection URL database {url_db!r}."
        )


args = parse_args()
configure_database(args)

from sqlalchemy import create_engine, delete, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.models import (  # noqa: E402
    Category,
    CategoryType,
    Collection,
    Item,
    ItemStatus,
    RecommendationHistory,
    RecommendationHistoryItem,
    StatusFilter,
    User,
)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def get_or_create_api_user(db, settings) -> User:
    """User matching SEED_USER_EMAIL so get_current_user works on RC Backend."""
    user = db.scalar(select(User).where(User.email == settings.seed_user_email))
    if user is not None:
        return user
    user = User(
        email=settings.seed_user_email,
        display_name=settings.seed_user_display_name,
        password_hash=hash_password(settings.seed_user_password),
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def clear_user_catalog(db, user_id) -> None:
    """Remove recommendation rows then items/collections/categories for one user."""
    history_ids = list(
        db.scalars(
            select(RecommendationHistory.id).where(
                RecommendationHistory.user_id == user_id
            )
        )
    )
    if history_ids:
        db.execute(
            delete(RecommendationHistoryItem).where(
                RecommendationHistoryItem.recommendation_history_id.in_(history_ids)
            )
        )
        db.execute(
            delete(RecommendationHistory).where(RecommendationHistory.id.in_(history_ids))
        )
    db.execute(delete(Item).where(Item.user_id == user_id))
    db.execute(delete(Collection).where(Collection.user_id == user_id))
    db.execute(delete(Category).where(Category.user_id == user_id))
    db.flush()


def bootstrap(db, settings, *, reset: bool) -> dict[str, int]:
    user = get_or_create_api_user(db, settings)
    if reset:
        clear_user_catalog(db, user.id)

    cats = {
        "영화": Category(
            user_id=user.id, name="영화", category_type=CategoryType.MEDIA, sort_order=1
        ),
        "드라마": Category(
            user_id=user.id, name="드라마", category_type=CategoryType.MEDIA, sort_order=2
        ),
        "도서": Category(
            user_id=user.id, name="도서", category_type=CategoryType.MEDIA, sort_order=3
        ),
    }
    for cat in cats.values():
        existing = db.scalar(
            select(Category).where(
                Category.user_id == user.id, Category.name == cat.name
            )
        )
        if existing is None:
            db.add(cat)
        else:
            cats[cat.name] = existing
    db.flush()

    def get_or_create_collection(name: str) -> Collection:
        existing = db.scalar(
            select(Collection).where(
                Collection.user_id == user.id, Collection.name == name
            )
        )
        if existing is not None:
            return existing
        col = Collection(user_id=user.id, name=name)
        db.add(col)
        db.flush()
        return col

    col_empty = get_or_create_collection("RC Empty")
    col_single = get_or_create_collection("RC Single")
    col_multi = get_or_create_collection("RC Multi")
    col_rename = get_or_create_collection("RC Rename Target")
    db.flush()

    def ensure_item(
        *,
        title: str,
        category: Category,
        collection: Collection | None,
        status: ItemStatus,
        rating: float = 0,
    ) -> Item:
        existing = db.scalar(
            select(Item).where(Item.user_id == user.id, Item.title == title)
        )
        if existing is not None:
            existing.category_id = category.id
            existing.collection_id = collection.id if collection else None
            existing.status = status
            existing.rating = rating
            return existing
        item = Item(
            user_id=user.id,
            category_id=category.id,
            collection_id=collection.id if collection else None,
            title=title,
            status=status,
            rating=rating,
        )
        db.add(item)
        db.flush()
        return item

    ensure_item(
        title="RC Single Item",
        category=cats["영화"],
        collection=col_single,
        status=ItemStatus.PLANNED,
    )
    ensure_item(
        title="RC Multi Planned",
        category=cats["영화"],
        collection=col_multi,
        status=ItemStatus.PLANNED,
    )
    ensure_item(
        title="RC Multi Completed",
        category=cats["드라마"],
        collection=col_multi,
        status=ItemStatus.COMPLETED,
        rating=3.5,
    )
    ensure_item(
        title="RC Standalone Planned",
        category=cats["영화"],
        collection=None,
        status=ItemStatus.PLANNED,
    )
    ensure_item(
        title="RC Standalone Completed",
        category=cats["도서"],
        collection=None,
        status=ItemStatus.COMPLETED,
        rating=4.0,
    )
    ensure_item(
        title="RC Long Title Item " + ("가" * 80),
        category=cats["영화"],
        collection=None,
        status=ItemStatus.PLANNED,
    )
    history_item = ensure_item(
        title="RC History Item",
        category=cats["영화"],
        collection=None,
        status=ItemStatus.PLANNED,
    )
    db.flush()

    # One recommendation history for snapshot QA (optional)
    existing_hist = db.scalar(
        select(RecommendationHistory).where(
            RecommendationHistory.user_id == user.id,
            RecommendationHistory.category_id == cats["영화"].id,
        )
    )
    if existing_hist is None:
        hist = RecommendationHistory(
            user_id=user.id,
            category_id=cats["영화"].id,
            status_filter=StatusFilter.ALL,
        )
        db.add(hist)
        db.flush()
        db.add(
            RecommendationHistoryItem(
                recommendation_history_id=hist.id,
                item_id=history_item.id,
                title_snapshot="RC History Item",
                status_at_selection=ItemStatus.PLANNED,
                sort_order=0,
            )
        )

    db.commit()

    from sqlalchemy import func

    items_n = db.scalar(select(func.count()).select_from(Item).where(Item.user_id == user.id)) or 0
    cols_n = db.scalar(
        select(func.count()).select_from(Collection).where(Collection.user_id == user.id)
    ) or 0
    cats_n = db.scalar(
        select(func.count()).select_from(Category).where(Category.user_id == user.id)
    ) or 0
    return {
        "categories": int(cats_n),
        "collections": int(cols_n),
        "items": int(items_n),
        "rc_empty_id_ok": 1 if col_empty.id else 0,
        "rc_rename_id_ok": 1 if col_rename.id else 0,
    }


def main() -> int:
    settings = get_settings()
    assert_safe_database(settings)
    print(f"RC-2 bootstrap DB={settings.postgres_db!r} user={settings.seed_user_email!r}")

    engine = create_engine(settings.sqlalchemy_database_url, future=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with session_factory() as db:
        counts = bootstrap(db, settings, reset=args.reset_fixtures)
    print("Fixture counts:", counts)
    print("OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
