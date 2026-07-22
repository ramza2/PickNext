#!/usr/bin/env python3
"""I-1 isolated PostgreSQL Item POST/PATCH smoke (disposable DB only).

Safety:
  - Refuses the development seed database (``picknext``).
  - Only ``picknext_item_write_*`` database names (or an explicit ``DATABASE_URL`` whose
    database name matches that prefix) are accepted.
  - Does not run ``docker compose down -v`` or touch the seed volume.

Setup (one-time per disposable DB)::

  docker compose exec postgres psql -U picknext -c "CREATE DATABASE picknext_item_write_smoke"
  docker compose exec -e POSTGRES_DB=picknext_item_write_smoke backend alembic upgrade head

Run::

  docker compose exec -e POSTGRES_DB=picknext_item_write_smoke backend python scripts/i1_item_write_smoke.py

Cleanup (optional)::

  docker compose exec postgres psql -U picknext -c "DROP DATABASE picknext_item_write_smoke"
"""

from __future__ import annotations

import argparse
import os
import sys
from uuid import uuid4

FORBIDDEN_DB_NAMES = frozenset({"picknext"})
ALLOWED_DB_PREFIX = "picknext_item_write_"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "I-1 Item POST/PATCH smoke against a disposable PostgreSQL database "
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
    os.environ.setdefault("POSTGRES_DB", "picknext_item_write_smoke")


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
from sqlalchemy import create_engine, select  # noqa: E402
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
    LegacyImportItem,
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
            email=f"smoke-{uuid4().hex[:8]}@picknext.local",
            display_name="Smoke",
            password_hash="hash",
            is_active=True,
        )
        other = User(
            email=f"smoke-other-{uuid4().hex[:8]}@picknext.local",
            display_name="Other",
            password_hash="hash",
            is_active=True,
        )
        db.add_all([user, other])
        db.flush()

        cat = Category(
            user_id=user.id,
            name="SmokeCat",
            category_type=CategoryType.MEDIA,
            sort_order=1,
        )
        other_cat = Category(
            user_id=other.id,
            name="OtherCat",
            category_type=CategoryType.MEDIA,
            sort_order=1,
        )
        col_a = Collection(user_id=user.id, name="ColA")
        col_b = Collection(user_id=user.id, name="ColB")
        other_col = Collection(user_id=other.id, name="OtherCol")
        db.add_all([cat, other_cat, col_a, col_b, other_col])
        db.flush()
        db.commit()

        app = create_app()

        def _override_db():
            with session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_current_user] = lambda: user

        with TestClient(app) as client:
            print("I-1 Item write smoke")
            create = client.post(
                "/api/v1/items",
                json={"title": "Smoke Item", "category_id": str(cat.id)},
            )
            if not assert_status("POST minimal item", create, 201):
                return 1
            item_id = create.json()["id"]
            assert_status("GET detail", client.get(f"/api/v1/items/{item_id}"), 200)

            patch = client.patch(
                f"/api/v1/items/{item_id}",
                json={"title": "Smoke Updated", "status": "COMPLETED", "rating": 4.5},
            )
            if not assert_status("PATCH title/status/rating", patch, 200):
                return 1

            attach = client.patch(
                f"/api/v1/items/{item_id}",
                json={"collection_id": str(col_a.id)},
            )
            if not assert_status("PATCH attach collection", attach, 200):
                return 1
            col_a_before = client.get(f"/api/v1/collections/{col_a.id}").json()["updated_at"]

            move = client.patch(
                f"/api/v1/items/{item_id}",
                json={"collection_id": str(col_b.id)},
            )
            assert_status("PATCH move collection", move, 200)
            col_a_after = client.get(f"/api/v1/collections/{col_a.id}").json()
            if col_a_after["item_count"] != 0:
                fail("empty collection kept", f"item_count={col_a_after['item_count']}")
            else:
                ok("empty collection kept after move")
            if col_a_after["updated_at"] != col_a_before:
                fail("collection updated_at unchanged", "touched after item move")
            else:
                ok("collection updated_at unchanged after move")

            detach = client.patch(
                f"/api/v1/items/{item_id}",
                json={"collection_id": None},
            )
            assert_status("PATCH detach collection", detach, 200)
            assert_status("collection still exists", client.get(f"/api/v1/collections/{col_b.id}"), 200)

            before_noop = client.get(f"/api/v1/items/{item_id}").json()["updated_at"]
            noop = client.patch(
                f"/api/v1/items/{item_id}",
                json={"title": "  Smoke Updated  "},
            )
            if noop.status_code != 200:
                fail("PATCH noop", f"status {noop.status_code}")
            elif noop.json()["updated_at"] != before_noop:
                fail("PATCH noop updated_at", "changed on no-op")
            else:
                ok("PATCH noop preserves updated_at")

            assert_status(
                "other user category 404",
                client.post(
                    "/api/v1/items",
                    json={"title": "X", "category_id": str(other_cat.id)},
                ),
                404,
            )
            assert_status(
                "other user collection 404",
                client.post(
                    "/api/v1/items",
                    json={
                        "title": "X",
                        "category_id": str(cat.id),
                        "collection_id": str(other_col.id),
                    },
                ),
                404,
            )
            assert_status(
                "invalid rating 422",
                client.post(
                    "/api/v1/items",
                    json={"title": "Bad", "category_id": str(cat.id), "rating": 1.1},
                ),
                422,
            )
            assert_status("DELETE new item", client.delete(f"/api/v1/items/{item_id}"), 204)
            assert_status("GET after delete 404", client.get(f"/api/v1/items/{item_id}"), 404)

            with session_factory() as verify_db:
                from sqlalchemy import func

                mapping_count = verify_db.scalar(
                    select(func.count())
                    .select_from(LegacyImportItem)
                    .where(LegacyImportItem.item_id == item_id)
                )
                if mapping_count:
                    fail("legacy mapping", "unexpected mapping after POST")
                else:
                    ok("no legacy mapping for POST item")

        app.dependency_overrides.clear()

    print(f"\nResult: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
