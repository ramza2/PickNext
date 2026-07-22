#!/usr/bin/env python3
"""D-8 isolated PostgreSQL DELETE smoke (disposable DB only).

Safety:
  - Refuses the development seed database (``picknext``).
  - Only ``picknext_d8_*`` database names (or an explicit ``DATABASE_URL`` whose
    database name matches that prefix) are accepted.
  - Does not run ``docker compose down -v`` or touch the seed volume.
  - Failures affect only the target disposable database.
  - No passwords or fixed connection strings are embedded in this script.

Setup (one-time per disposable DB)::

  docker compose exec postgres psql -U picknext -c "CREATE DATABASE picknext_d8_smoke"
  docker compose exec -e POSTGRES_DB=picknext_d8_smoke backend alembic upgrade head

Run (idempotent; safe to re-run against the same disposable DB)::

  docker compose exec -e POSTGRES_DB=picknext_d8_smoke backend python scripts/d8_delete_smoke.py

Cleanup (optional, disposable DB only)::

  docker compose exec postgres psql -U picknext -c "DROP DATABASE picknext_d8_smoke"
"""

from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal
from uuid import uuid4

FORBIDDEN_DB_NAMES = frozenset({"picknext"})
ALLOWED_DB_PREFIX = "picknext_d8_"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "D-8 DELETE smoke against a disposable PostgreSQL database "
            f"(name must start with {ALLOWED_DB_PREFIX!r}, never the seed DB)."
        ),
        epilog=(
            "Example:\n"
            "  docker compose exec -e POSTGRES_DB=picknext_d8_smoke "
            "backend python scripts/d8_delete_smoke.py"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--postgres-db",
        metavar="NAME",
        help=f"Target database name (must start with {ALLOWED_DB_PREFIX!r})",
    )
    parser.add_argument(
        "--database-url",
        metavar="URL",
        help=(
            "Explicit SQLAlchemy database URL "
            f"(database name must start with {ALLOWED_DB_PREFIX!r})"
        ),
    )
    return parser.parse_args()


def configure_database(args: argparse.Namespace) -> None:
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    if args.postgres_db:
        os.environ["POSTGRES_DB"] = args.postgres_db
    os.environ.setdefault("POSTGRES_DB", "picknext_d8_smoke")


def assert_safe_database(settings) -> None:
    db_name = settings.postgres_db
    if db_name in FORBIDDEN_DB_NAMES:
        raise SystemExit(
            f"Refusing seed database {db_name!r}. "
            f"Create a disposable database named {ALLOWED_DB_PREFIX}* instead."
        )
    if not db_name.startswith(ALLOWED_DB_PREFIX):
        raise SystemExit(
            f"Refusing database {db_name!r}. "
            f"Only names starting with {ALLOWED_DB_PREFIX!r} are allowed."
        )

    url = settings.sqlalchemy_database_url
    url_db = getattr(url, "database", None) or ""
    if url_db in FORBIDDEN_DB_NAMES:
        raise SystemExit(
            f"Refusing connection URL database {url_db!r}. "
            f"Point DATABASE_URL at {ALLOWED_DB_PREFIX}* only."
        )
    if url_db and not url_db.startswith(ALLOWED_DB_PREFIX):
        raise SystemExit(
            f"Refusing connection URL database {url_db!r}. "
            f"Only {ALLOWED_DB_PREFIX}* is allowed."
        )


args = parse_args()
configure_database(args)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.api.deps import get_current_user  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import (  # noqa: E402
    Category,
    CategoryType,
    Collection,
    Item,
    ItemStatus,
    LegacyImportCollection,
    LegacyImportDisposition,
    LegacyImportItem,
    LegacyImportRun,
    LegacyImportRunStatus,
    RecommendationHistory,
    RecommendationHistoryItem,
    StatusFilter,
    User,
)

PASS = 0
FAIL = 0


def ok(name: str) -> None:
    global PASS
    PASS += 1
    print(f"  OK  {name}")


def fail(name: str, detail: str) -> None:
    global FAIL
    FAIL += 1
    print(f" FAIL {name}: {detail}")


def assert_status(
    name: str,
    response,
    expected: int,
    *,
    empty_body: bool = False,
) -> bool:
    if response.status_code != expected:
        fail(name, f"status {response.status_code}, expected {expected}")
        return False
    if empty_body and response.content not in (b"", None):
        fail(name, f"body not empty: {response.content!r}")
        return False
    ok(name)
    return True


def _category(db: Session, user: User, name: str) -> Category:
    cat = Category(
        user_id=user.id,
        name=name,
        category_type=CategoryType.MEDIA,
        sort_order=1,
    )
    db.add(cat)
    db.flush()
    return cat


def _collection(db: Session, user: User, name: str) -> Collection:
    col = Collection(user_id=user.id, name=name)
    db.add(col)
    db.flush()
    return col


def _item(
    db: Session,
    *,
    user: User,
    category: Category,
    title: str,
    collection: Collection | None = None,
) -> Item:
    item = Item(
        user_id=user.id,
        category_id=category.id,
        collection_id=collection.id if collection else None,
        title=title,
        status=ItemStatus.PLANNED,
        rating=Decimal("0.0"),
    )
    db.add(item)
    db.flush()
    return item


def _history(
    db: Session,
    *,
    user: User,
    category: Category,
    items: list[Item],
    collection: Collection | None = None,
) -> RecommendationHistory:
    history = RecommendationHistory(
        user_id=user.id,
        category_id=category.id,
        status_filter=StatusFilter.ALL,
        collection_id=collection.id if collection else None,
    )
    db.add(history)
    db.flush()
    for index, item in enumerate(items):
        db.add(
            RecommendationHistoryItem(
                recommendation_history_id=history.id,
                item_id=item.id,
                title_snapshot=item.title,
                status_at_selection=item.status,
                sort_order=index,
            )
        )
    db.flush()
    return history


def seed_fixtures(db: Session) -> dict:
    user_a = User(
        email=f"smoke-a-{uuid4().hex[:8]}@picknext.local",
        display_name="Smoke A",
        password_hash="hash",
        is_active=True,
    )
    user_b = User(
        email=f"smoke-b-{uuid4().hex[:8]}@picknext.local",
        display_name="Smoke B",
        password_hash="hash",
        is_active=True,
    )
    db.add_all([user_a, user_b])
    db.flush()

    cat_a = _category(db, user_a, "SmokeCat")
    cat_b = _category(db, user_b, "OtherCat")

    c_empty = _collection(db, user_a, "C_EMPTY")
    c_one = _collection(db, user_a, "C_ONE")
    c_multi = _collection(db, user_a, "C_MULTI")
    c_history_only = _collection(db, user_a, "C_HISTORY_ONLY")
    c_legacy_empty = _collection(db, user_a, "C_LEGACY_EMPTY")

    i_standalone = _item(db, user=user_a, category=cat_a, title="I_STANDALONE")
    i_last = _item(db, user=user_a, category=cat_a, title="I_LAST", collection=c_one)
    i_keep = _item(db, user=user_a, category=cat_a, title="I_KEEP", collection=c_multi)
    i_delete = _item(db, user=user_a, category=cat_a, title="I_DELETE", collection=c_multi)
    i_other_user = _item(db, user=user_b, category=cat_b, title="I_OTHER_USER")

    sibling1 = _item(db, user=user_a, category=cat_a, title="SIB1")
    sibling2 = _item(db, user=user_a, category=cat_a, title="SIB2")
    i_history = _item(db, user=user_a, category=cat_a, title="I_HISTORY")
    r1 = _history(db, user=user_a, category=cat_a, items=[i_history, sibling1])
    r2 = _history(db, user=user_a, category=cat_a, items=[i_history, sibling2])
    r_keep = _history(db, user=user_a, category=cat_a, items=[sibling1])
    r_col_ref = _history(
        db, user=user_a, category=cat_a, items=[sibling1], collection=c_history_only
    )
    r_one_ref = _history(db, user=user_a, category=cat_a, items=[sibling1], collection=c_one)

    run = LegacyImportRun(
        user_id=user_a.id,
        source_filename="d8-smoke.json",
        source_sha256=uuid4().hex,
        source_total_count=2,
        imported_item_count=2,
        skipped_count=0,
        status=LegacyImportRunStatus.SUCCESS,
    )
    db.add(run)
    db.flush()
    legacy_item = LegacyImportItem(
        import_run_id=run.id,
        item_id=i_history.id,
        source_id=1,
        disposition=LegacyImportDisposition.IMPORTED,
    )
    legacy_col = LegacyImportCollection(
        import_run_id=run.id,
        collection_id=c_legacy_empty.id,
        collection_name=c_legacy_empty.name,
    )
    db.add_all([legacy_item, legacy_col])
    db.flush()

    db.commit()

    return {
        "user_a": user_a,
        "user_b": user_b,
        "c_empty": c_empty,
        "c_one": c_one,
        "c_multi": c_multi,
        "c_history_only": c_history_only,
        "c_legacy_empty": c_legacy_empty,
        "i_standalone": i_standalone,
        "i_history": i_history,
        "i_last": i_last,
        "i_delete": i_delete,
        "i_keep": i_keep,
        "i_other_user": i_other_user,
        "r1": r1,
        "r2": r2,
        "r_keep": r_keep,
        "r_col_ref": r_col_ref,
        "r_one_ref": r_one_ref,
        "legacy_item_id": legacy_item.id,
        "legacy_col_id": legacy_col.id,
        "run_id": run.id,
    }


def make_client(db: Session, user: User) -> TestClient:
    app = create_app()

    def _db():
        yield db

    def _user():
        return user

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user
    return TestClient(app)


def run_smoke() -> int:
    settings = get_settings()
    assert_safe_database(settings)

    engine = create_engine(settings.sqlalchemy_database_url, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with SessionLocal() as db:
        fx = seed_fixtures(db)
        user_a = fx["user_a"]
        client = make_client(db, user_a)

        print("=== 13.1 standalone item ===")
        r = client.delete(f"/api/v1/items/{fx['i_standalone'].id}")
        assert_status("DELETE I_STANDALONE 204", r, 204, empty_body=True)
        assert_status("re-delete 404", client.delete(f"/api/v1/items/{fx['i_standalone'].id}"), 404)

        print("=== 13.2 history item ===")
        r1_id, r2_id, r_keep_id = fx["r1"].id, fx["r2"].id, fx["r_keep"].id
        hist_id = fx["i_history"].id
        legacy_item_id = fx["legacy_item_id"]
        r = client.delete(f"/api/v1/items/{hist_id}")
        assert_status("DELETE I_HISTORY 204", r, 204, empty_body=True)
        if db.get(RecommendationHistory, r1_id) is None:
            ok("R1 deleted")
        else:
            fail("R1 deleted", "still exists")
        if db.get(RecommendationHistory, r2_id) is None:
            ok("R2 deleted")
        else:
            fail("R2 deleted", "still exists")
        if db.get(RecommendationHistory, r_keep_id) is not None:
            ok("R_KEEP kept")
        else:
            fail("R_KEEP kept", "missing")
        if db.get(LegacyImportItem, legacy_item_id) is None:
            ok("legacy item mapping cascade")
        else:
            fail("legacy item mapping cascade", "still exists")

        print("=== 13.3 non-last collection item ===")
        c_multi_id = fx["c_multi"].id
        i_delete_id = fx["i_delete"].id
        i_keep_id = fx["i_keep"].id
        r = client.delete(f"/api/v1/items/{i_delete_id}")
        assert_status("DELETE I_DELETE 204", r, 204, empty_body=True)
        if db.get(Collection, c_multi_id) is not None:
            ok("C_MULTI kept")
        else:
            fail("C_MULTI kept", "gone")
        if db.get(Item, i_keep_id) and db.get(Item, i_keep_id).collection_id == c_multi_id:
            ok("I_KEEP link kept")
        else:
            fail("I_KEEP link kept", "broken")

        print("=== 13.4 last item auto collection delete ===")
        c_one_id = fx["c_one"].id
        i_last_id = fx["i_last"].id
        r_one_ref_id = fx["r_one_ref"].id
        r = client.delete(f"/api/v1/items/{i_last_id}")
        assert_status("DELETE I_LAST 204", r, 204, empty_body=True)
        if db.get(Collection, c_one_id) is None:
            ok("C_ONE auto deleted")
        else:
            fail("C_ONE auto deleted", "still exists")
        assert_status("C_ONE detail 404", client.get(f"/api/v1/collections/{c_one_id}"), 404)
        kept_hist = db.get(RecommendationHistory, r_one_ref_id)
        if kept_hist and kept_hist.collection_id is None:
            ok("R_ONE_REF collection_id NULL after C_ONE auto delete")
        else:
            fail("R_ONE_REF collection_id NULL", "wrong state")

        print("=== 13.5 empty collection delete ===")
        c_empty_id = fx["c_empty"].id
        r = client.delete(f"/api/v1/collections/{c_empty_id}")
        assert_status("DELETE C_EMPTY 204", r, 204, empty_body=True)
        assert_status("re-delete C_EMPTY 404", client.delete(f"/api/v1/collections/{c_empty_id}"), 404)

        print("=== 13.6 collection with items 409 ===")
        r = client.delete(f"/api/v1/collections/{c_multi_id}")
        assert_status("DELETE C_MULTI 409", r, 409)
        if db.get(Item, i_keep_id) and db.get(Item, i_keep_id).collection_id == c_multi_id:
            ok("no unlink on 409")
        else:
            fail("no unlink on 409", "item unlinked")

        print("=== 13.7 history-only empty collection ===")
        c_hist_id = fx["c_history_only"].id
        r_col_ref_id = fx["r_col_ref"].id
        r = client.delete(f"/api/v1/collections/{c_hist_id}")
        assert_status("DELETE C_HISTORY_ONLY 204", r, 204, empty_body=True)
        if db.get(RecommendationHistory, r_col_ref_id) is not None:
            ok("history kept")
        else:
            fail("history kept", "deleted")
        if db.get(RecommendationHistory, r_col_ref_id).collection_id is None:
            ok("history collection_id NULL")
        else:
            fail("history collection_id NULL", "not null")

        print("=== 13.8 legacy empty collection ===")
        c_legacy_id = fx["c_legacy_empty"].id
        legacy_col_id = fx["legacy_col_id"]
        run_id = fx["run_id"]
        imported_before = db.get(LegacyImportRun, run_id).imported_item_count
        r = client.delete(f"/api/v1/collections/{c_legacy_id}")
        assert_status("DELETE C_LEGACY_EMPTY 204", r, 204, empty_body=True)
        if db.get(LegacyImportCollection, legacy_col_id) is None:
            ok("legacy collection mapping cascade")
        else:
            fail("legacy collection mapping cascade", "still exists")
        if db.get(LegacyImportRun, run_id).imported_item_count == imported_before:
            ok("import run stats kept")
        else:
            fail("import run stats kept", "changed")

        print("=== 13.9 user scope ===")
        other_item_id = fx["i_other_user"].id
        assert_status("other user item 404", client.delete(f"/api/v1/items/{other_item_id}"), 404)
        if db.get(Item, other_item_id) is not None:
            ok("other user item kept")
        else:
            fail("other user item kept", "deleted")

        print("=== 21 concurrency double delete ===")
        r = client.delete(f"/api/v1/items/{i_keep_id}")
        assert_status("first I_KEEP delete 204", r, 204, empty_body=True)
        assert_status("second I_KEEP delete 404", client.delete(f"/api/v1/items/{i_keep_id}"), 404)

    engine.dispose()
    print(f"\nD-8 smoke: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run_smoke())
