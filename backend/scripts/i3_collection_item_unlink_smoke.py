#!/usr/bin/env python3
"""I-3 isolated PostgreSQL Collection Item unlink / write-policy smoke.

Safety:
  - Refuses the development seed database (``picknext``).
  - Only ``picknext_i3_write_*`` database names are accepted.
  - Does not run ``docker compose down -v`` or touch the seed volume.

Setup::

  docker compose exec postgres psql -U picknext -c "CREATE DATABASE picknext_i3_write_regression"
  docker compose exec -e POSTGRES_DB=picknext_i3_write_regression backend alembic upgrade head

Run::

  docker compose exec -e POSTGRES_DB=picknext_i3_write_regression \\
    backend python scripts/i3_collection_item_unlink_smoke.py

Cleanup (optional)::

  docker compose exec postgres psql -U picknext -c "DROP DATABASE picknext_i3_write_regression"
"""

from __future__ import annotations

import argparse
import os
import sys
from uuid import uuid4

FORBIDDEN_DB_NAMES = frozenset({"picknext"})
ALLOWED_DB_PREFIX = "picknext_i3_write_"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "I-3 Collection Item unlink smoke against a disposable PostgreSQL database "
            f"(name must start with {ALLOWED_DB_PREFIX!r}, never the seed DB)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--postgres-db", metavar="NAME")
    parser.add_argument("--database-url", metavar="URL")
    return parser.parse_args()


def configure_database(args: argparse.Namespace) -> None:
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    if args.postgres_db:
        os.environ["POSTGRES_DB"] = args.postgres_db
    os.environ.setdefault("POSTGRES_DB", "picknext_i3_write_regression")


def assert_safe_database(settings) -> None:
    db_name = settings.postgres_db
    if db_name in FORBIDDEN_DB_NAMES:
        raise SystemExit(f"Refusing seed database {db_name!r}.")
    if not db_name.startswith(ALLOWED_DB_PREFIX):
        raise SystemExit(
            f"Refusing database {db_name!r}. Only {ALLOWED_DB_PREFIX}* is allowed."
        )
    url_db = getattr(settings.sqlalchemy_database_url, "database", None) or ""
    if url_db in FORBIDDEN_DB_NAMES:
        raise SystemExit(f"Refusing connection URL database {url_db!r}.")
    if url_db and not url_db.startswith(ALLOWED_DB_PREFIX):
        raise SystemExit(f"Refusing connection URL database {url_db!r}.")


args = parse_args()
configure_database(args)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

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


def assert_status(name: str, response, expected: int) -> bool:
    if response.status_code != expected:
        fail(name, f"status {response.status_code}, expected {expected}")
        return False
    ok(name)
    return True


def main() -> int:
    settings = get_settings()
    assert_safe_database(settings)

    engine = create_engine(settings.sqlalchemy_database_url, future=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with session_factory() as db:
        user = User(
            email=f"i3-{uuid4().hex[:8]}@picknext.local",
            display_name="I3",
            password_hash="hash",
            is_active=True,
        )
        other = User(
            email=f"i3-other-{uuid4().hex[:8]}@picknext.local",
            display_name="Other",
            password_hash="hash",
            is_active=True,
        )
        db.add_all([user, other])
        db.flush()

        cat = Category(
            user_id=user.id,
            name="I3Cat",
            category_type=CategoryType.MEDIA,
            sort_order=1,
        )
        multi = Collection(user_id=user.id, name="Multi")
        last_one = Collection(user_id=user.id, name="LastOne")
        empty = Collection(user_id=user.id, name="Empty")
        other_col = Collection(user_id=other.id, name="OtherCol")
        db.add_all([cat, multi, last_one, empty, other_col])
        db.flush()

        item_a = Item(
            user_id=user.id,
            category_id=cat.id,
            collection_id=multi.id,
            title="Item A",
            status=ItemStatus.PLANNED,
            rating=0,
        )
        item_b = Item(
            user_id=user.id,
            category_id=cat.id,
            collection_id=multi.id,
            title="Item B",
            status=ItemStatus.COMPLETED,
            rating=0,
        )
        item_last = Item(
            user_id=user.id,
            category_id=cat.id,
            collection_id=last_one.id,
            title="Only Item",
            status=ItemStatus.PLANNED,
            rating=0,
        )
        item_free = Item(
            user_id=user.id,
            category_id=cat.id,
            collection_id=None,
            title="Unlinked",
            status=ItemStatus.PLANNED,
            rating=0,
        )
        other_cat = Category(
            user_id=other.id,
            name="OtherCat",
            category_type=CategoryType.MEDIA,
            sort_order=1,
        )
        db.add(other_cat)
        db.flush()
        other_item = Item(
            user_id=other.id,
            category_id=other_cat.id,
            collection_id=other_col.id,
            title="Other Item",
            status=ItemStatus.PLANNED,
            rating=0,
        )
        db.add_all([item_a, item_b, item_last, item_free, other_item])
        db.flush()

        history = RecommendationHistory(
            user_id=user.id,
            category_id=cat.id,
            collection_id=multi.id,
            status_filter=StatusFilter.ALL,
        )
        db.add(history)
        db.flush()
        history_item = RecommendationHistoryItem(
            recommendation_history_id=history.id,
            item_id=item_a.id,
            title_snapshot="Item A",
            status_at_selection=ItemStatus.PLANNED,
            sort_order=0,
        )
        db.add(history_item)
        db.commit()

        item_a_id = item_a.id
        item_b_id = item_b.id
        item_last_id = item_last.id
        item_free_id = item_free.id
        other_item_id = other_item.id
        multi_id = multi.id
        last_one_id = last_one.id
        empty_id = empty.id
        history_id = history.id
        history_item_id = history_item.id
        cat_id = cat.id

        app = create_app()

        def _override_db():
            with session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_current_user] = lambda: user

        with TestClient(app) as client:
            print("I-3 Collection Item unlink smoke")

            # Multi: unlink A, keep B + collection
            unlink_a = client.patch(
                f"/api/v1/items/{item_a_id}",
                json={"collection_id": None},
            )
            if assert_status("unlink A from multi", unlink_a, 200):
                body = unlink_a.json()
                if body.get("collection") is not None:
                    fail("unlink A response collection", "expected null")
                else:
                    ok("unlink A response collection null")
                if body.get("id") != str(item_a_id):
                    fail("unlink A id", body.get("id"))
                else:
                    ok("unlink A item id preserved")

            multi_after = client.get(f"/api/v1/collections/{multi_id}")
            if assert_status("multi collection kept", multi_after, 200):
                data = multi_after.json()
                if data["item_count"] != 1:
                    fail("multi item_count", str(data["item_count"]))
                else:
                    ok("multi item_count=1")
                if data["completed_count"] != 1 or data["planned_count"] != 0:
                    fail(
                        "multi status counts",
                        f"planned={data['planned_count']} completed={data['completed_count']}",
                    )
                else:
                    ok("multi status counts after unlink")

            get_a = client.get(f"/api/v1/items/{item_a_id}")
            if assert_status("item A still exists", get_a, 200):
                if get_a.json().get("collection") is not None:
                    fail("item A collection", "expected null")
                else:
                    ok("item A collection null")

            get_b = client.get(f"/api/v1/items/{item_b_id}")
            if assert_status("item B still linked", get_b, 200):
                col = get_b.json().get("collection") or {}
                if col.get("id") != str(multi_id):
                    fail("item B collection", str(col))
                else:
                    ok("item B still on multi")

            # Last item unlink → empty collection kept
            unlink_last = client.patch(
                f"/api/v1/items/{item_last_id}",
                json={"collection_id": None},
            )
            if assert_status("unlink last item", unlink_last, 200):
                if unlink_last.json().get("collection") is not None:
                    fail("last unlink collection", "expected null")
                else:
                    ok("last unlink response collection null")

            last_col = client.get(f"/api/v1/collections/{last_one_id}")
            if assert_status("empty collection kept after last unlink", last_col, 200):
                data = last_col.json()
                if data["item_count"] != 0:
                    fail("last collection item_count", str(data["item_count"]))
                else:
                    ok("last collection item_count=0")
                if data.get("categories"):
                    fail("last collection categories", str(data["categories"]))
                else:
                    ok("last collection categories=[]")

            assert_status(
                "last item still exists",
                client.get(f"/api/v1/items/{item_last_id}"),
                200,
            )

            # Already unlinked noop
            free_before = client.get(f"/api/v1/items/{item_free_id}").json()["updated_at"]
            noop = client.patch(
                f"/api/v1/items/{item_free_id}",
                json={"collection_id": None},
            )
            if assert_status("noop unlink already null", noop, 200):
                if noop.json()["updated_at"] != free_before:
                    fail("noop updated_at", "changed")
                else:
                    ok("noop unlink preserves updated_at")

            # Other user 404
            assert_status(
                "other user item unlink 404",
                client.patch(
                    f"/api/v1/items/{other_item_id}",
                    json={"collection_id": None},
                ),
                404,
            )

            # Status toggle on remaining linked item
            status = client.patch(
                f"/api/v1/items/{item_b_id}",
                json={"status": "PLANNED"},
            )
            if assert_status("status toggle remaining item", status, 200):
                if status.json()["status"] != "PLANNED":
                    fail("status value", status.json()["status"])
                else:
                    ok("status toggled to PLANNED")
            multi_status = client.get(f"/api/v1/collections/{multi_id}").json()
            if multi_status["planned_count"] != 1 or multi_status["completed_count"] != 0:
                fail(
                    "counts after status",
                    f"p={multi_status['planned_count']} c={multi_status['completed_count']}",
                )
            else:
                ok("counts after status toggle")
            if multi_status.get("collection") is not None:
                pass  # n/a
            if multi_status["item_count"] != 1:
                fail("item_count after status", str(multi_status["item_count"]))
            else:
                ok("collection kept after status")

            # History snapshot unchanged after unlink
            with session_factory() as verify_db:
                hi = verify_db.get(RecommendationHistoryItem, history_item_id)
                if hi is None:
                    fail("history item", "missing")
                elif hi.title_snapshot != "Item A" or hi.status_at_selection != ItemStatus.PLANNED:
                    fail("history snapshot", f"{hi.title_snapshot}/{hi.status_at_selection}")
                else:
                    ok("history snapshot unchanged")
                hist = verify_db.get(RecommendationHistory, history_id)
                if hist is None:
                    fail("history parent", "missing")
                else:
                    ok("history parent kept")

            # Empty collection DELETE allowed
            assert_status(
                "delete empty collection",
                client.delete(f"/api/v1/collections/{empty_id}"),
                204,
            )

            # Policy contrast: DELETE last remaining on multi → auto-delete empty?
            # After unlink A and status on B, multi has only B. DELETE B should auto-delete multi.
            delete_b = client.delete(f"/api/v1/items/{item_b_id}")
            assert_status("DELETE remaining item B", delete_b, 204)
            multi_gone = client.get(f"/api/v1/collections/{multi_id}")
            if multi_gone.status_code == 404:
                ok("DELETE last item auto-deletes collection")
            else:
                fail(
                    "DELETE last item collection policy",
                    f"status {multi_gone.status_code} (expected 404)",
                )

            # Form-style create + unlink keep empty
            create_col = client.post("/api/v1/collections", json={"name": "FormEmpty"})
            if not assert_status("create collection", create_col, 201):
                return 1
            form_col_id = create_col.json()["id"]
            create_item = client.post(
                "/api/v1/items",
                json={
                    "title": "Form Item",
                    "category_id": str(cat_id),
                    "collection_id": form_col_id,
                },
            )
            if not assert_status("create item in collection", create_item, 201):
                return 1
            form_item_id = create_item.json()["id"]
            unlink_form = client.patch(
                f"/api/v1/items/{form_item_id}",
                json={"collection_id": None},
            )
            assert_status("form-style unlink", unlink_form, 200)
            assert_status(
                "form collection kept empty",
                client.get(f"/api/v1/collections/{form_col_id}"),
                200,
            )
            assert_status(
                "form item kept",
                client.get(f"/api/v1/items/{form_item_id}"),
                200,
            )

        app.dependency_overrides.clear()

    print(f"\nResult: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
