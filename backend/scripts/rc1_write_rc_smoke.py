#!/usr/bin/env python3
"""RC-1 isolated PostgreSQL write Release Candidate smoke + fixture bootstrap.

Safety:
  - Refuses seed/default DBs (``picknext``, ``postgres``).
  - Requires an explicit ``--postgres-db`` / ``POSTGRES_DB`` / ``DATABASE_URL``.
  - Only ``picknext_write_rc`` (exact) or ``picknext_write_rc_*`` names are accepted.
  - Does not run ``docker compose down -v``, drop databases, or touch the seed volume.

Setup::

  docker compose exec postgres psql -U picknext -c "CREATE DATABASE picknext_write_rc"
  docker compose exec -e POSTGRES_DB=picknext_write_rc backend alembic upgrade head

Run::

  docker compose cp backend/scripts/rc1_write_rc_smoke.py backend:/app/rc1_write_rc_smoke.py
  docker compose exec -e POSTGRES_DB=picknext_write_rc backend \\
    python rc1_write_rc_smoke.py --postgres-db picknext_write_rc

This script validates write API contracts that map to browser QA scenarios.
It does **not** replace Desktop/Mobile visual, Console, or Network browser QA.
"""

from __future__ import annotations

import argparse
import os
import sys
from uuid import uuid4

FORBIDDEN_DB_NAMES = frozenset({"picknext", "postgres"})
ALLOWED_EXACT = frozenset({"picknext_write_rc"})
ALLOWED_PREFIX = "picknext_write_rc_"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "RC-1 write smoke against disposable PostgreSQL "
            f"(name must be {sorted(ALLOWED_EXACT)!r} or start with {ALLOWED_PREFIX!r}). "
            "POSTGRES_DB or --postgres-db is required."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--postgres-db",
        metavar="NAME",
        help="Isolated database name (required unless POSTGRES_DB/DATABASE_URL already set).",
    )
    parser.add_argument("--database-url", metavar="URL")
    return parser.parse_args()


def configure_database(args: argparse.Namespace) -> None:
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    if args.postgres_db:
        os.environ["POSTGRES_DB"] = args.postgres_db
    # Do not default to any database — caller must pass an isolated name explicitly.
    if not args.database_url and not os.environ.get("POSTGRES_DB"):
        raise SystemExit(
            "RC smoke requires an explicit isolated database. "
            "Pass --postgres-db picknext_write_rc or set POSTGRES_DB=picknext_write_rc."
        )


def assert_safe_database(settings) -> None:
    db_name = (settings.postgres_db or "").strip()
    if not db_name:
        raise RuntimeError(
            "RC smoke requires an explicit isolated database "
            "(--postgres-db or POSTGRES_DB)."
        )
    if db_name in FORBIDDEN_DB_NAMES:
        raise RuntimeError(
            f"RC smoke must run against an isolated database (refused {db_name!r})."
        )
    if db_name not in ALLOWED_EXACT and not db_name.startswith(ALLOWED_PREFIX):
        raise RuntimeError(
            f"RC smoke must run against an isolated database "
            f"(refused {db_name!r}; allowed {sorted(ALLOWED_EXACT)!r} or {ALLOWED_PREFIX}*)."
        )
    url_db = getattr(settings.sqlalchemy_database_url, "database", None) or ""
    url_db = str(url_db).strip()
    if url_db in FORBIDDEN_DB_NAMES:
        raise RuntimeError(
            f"RC smoke must run against an isolated database "
            f"(refused connection URL database {url_db!r})."
        )
    if url_db and url_db not in ALLOWED_EXACT and not url_db.startswith(ALLOWED_PREFIX):
        raise RuntimeError(
            f"RC smoke must run against an isolated database "
            f"(refused connection URL database {url_db!r})."
        )


args = parse_args()
configure_database(args)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, func, select  # noqa: E402
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


def assert_status(name: str, response, expected: int) -> bool:
    if response.status_code != expected:
        fail(name, f"status {response.status_code}, expected {expected}")
        return False
    ok(name)
    return True


def main() -> int:
    settings = get_settings()
    assert_safe_database(settings)
    print(f"RC-1 write smoke DB={settings.postgres_db!r}")

    engine = create_engine(settings.sqlalchemy_database_url, future=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with session_factory() as db:
        # Idempotent-ish: unique emails per run so re-runs do not collide.
        run_tag = uuid4().hex[:8]
        user = User(
            email=f"rc1-{run_tag}@picknext.local",
            display_name="RC1 User",
            password_hash="hash",
            is_active=True,
        )
        other = User(
            email=f"rc1-other-{run_tag}@picknext.local",
            display_name="RC1 Other",
            password_hash="hash",
            is_active=True,
        )
        db.add_all([user, other])
        db.flush()

        cat_movie = Category(
            user_id=user.id, name="영화", category_type=CategoryType.MEDIA, sort_order=1
        )
        cat_drama = Category(
            user_id=user.id, name="드라마", category_type=CategoryType.MEDIA, sort_order=2
        )
        cat_book = Category(
            user_id=user.id, name="도서", category_type=CategoryType.MEDIA, sort_order=3
        )
        other_cat = Category(
            user_id=other.id,
            name="OtherCat",
            category_type=CategoryType.MEDIA,
            sort_order=1,
        )
        db.add_all([cat_movie, cat_drama, cat_book, other_cat])
        db.flush()

        col_empty = Collection(user_id=user.id, name="RC Empty")
        col_single = Collection(user_id=user.id, name="RC Single")
        col_multi = Collection(user_id=user.id, name="RC Multi")
        col_rename = Collection(user_id=user.id, name="RC Rename Target")
        other_col = Collection(user_id=other.id, name="Other Collection")
        db.add_all([col_empty, col_single, col_multi, col_rename, other_col])
        db.flush()

        item_single = Item(
            user_id=user.id,
            category_id=cat_movie.id,
            collection_id=col_single.id,
            title="RC Single Item",
            status=ItemStatus.PLANNED,
            rating=0,
        )
        item_multi_planned = Item(
            user_id=user.id,
            category_id=cat_movie.id,
            collection_id=col_multi.id,
            title="RC Multi Planned",
            status=ItemStatus.PLANNED,
            rating=0,
        )
        item_multi_completed = Item(
            user_id=user.id,
            category_id=cat_drama.id,
            collection_id=col_multi.id,
            title="RC Multi Completed",
            status=ItemStatus.COMPLETED,
            rating=3.5,
        )
        item_standalone_planned = Item(
            user_id=user.id,
            category_id=cat_movie.id,
            collection_id=None,
            title="RC Standalone Planned",
            status=ItemStatus.PLANNED,
            rating=0,
        )
        item_standalone_completed = Item(
            user_id=user.id,
            category_id=cat_book.id,
            collection_id=None,
            title="RC Standalone Completed",
            status=ItemStatus.COMPLETED,
            rating=4.0,
        )
        item_long = Item(
            user_id=user.id,
            category_id=cat_movie.id,
            collection_id=None,
            title="RC Long Title Item " + ("가" * 80),
            status=ItemStatus.PLANNED,
            rating=0,
        )
        item_with_history = Item(
            user_id=user.id,
            category_id=cat_movie.id,
            collection_id=None,
            title="RC History Item",
            status=ItemStatus.PLANNED,
            rating=0,
        )
        item_legacy = Item(
            user_id=user.id,
            category_id=cat_movie.id,
            collection_id=None,
            title="RC Legacy Mapped Item",
            status=ItemStatus.PLANNED,
            rating=0,
        )
        other_item = Item(
            user_id=other.id,
            category_id=other_cat.id,
            collection_id=other_col.id,
            title="Other Item",
            status=ItemStatus.PLANNED,
            rating=0,
        )
        db.add_all(
            [
                item_single,
                item_multi_planned,
                item_multi_completed,
                item_standalone_planned,
                item_standalone_completed,
                item_long,
                item_with_history,
                item_legacy,
                other_item,
            ]
        )
        db.flush()

        history = RecommendationHistory(
            user_id=user.id,
            category_id=cat_movie.id,
            status_filter=StatusFilter.ALL,
        )
        db.add(history)
        db.flush()
        db.add(
            RecommendationHistoryItem(
                recommendation_history_id=history.id,
                item_id=item_with_history.id,
                title_snapshot="RC History Item",
                status_at_selection=ItemStatus.PLANNED,
                sort_order=0,
            )
        )

        legacy_run = LegacyImportRun(
            user_id=user.id,
            source_filename="rc1-fixture.json",
            source_sha256=uuid4().hex,
            source_total_count=1,
            imported_item_count=1,
            skipped_count=0,
            status=LegacyImportRunStatus.SUCCESS,
        )
        db.add(legacy_run)
        db.flush()
        db.add(
            LegacyImportItem(
                import_run_id=legacy_run.id,
                item_id=item_legacy.id,
                source_id=900001,
                disposition=LegacyImportDisposition.IMPORTED,
            )
        )
        db.commit()

        ids = {
            "user": user.id,
            "movie": cat_movie.id,
            "drama": cat_drama.id,
            "empty": col_empty.id,
            "single": col_single.id,
            "multi": col_multi.id,
            "rename": col_rename.id,
            "single_item": item_single.id,
            "multi_planned": item_multi_planned.id,
            "multi_completed": item_multi_completed.id,
            "standalone": item_standalone_planned.id,
            "history_item": item_with_history.id,
            "legacy_item": item_legacy.id,
            "other_item": other_item.id,
            "history": history.id,
            "legacy_run": legacy_run.id,
        }

        app = create_app()

        def _override_db():
            with session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_current_user] = lambda: user

        with TestClient(app) as client:
            print("RC-1 Collection CRUD")
            create = client.post(
                "/api/v1/collections",
                json={"name": "RC Browser Collection"},
            )
            if not assert_status("collection POST 201", create, 201):
                return 1
            browser_col_id = create.json()["id"]
            if create.json().get("item_count") != 0:
                fail("collection create empty", str(create.json().get("item_count")))
            else:
                ok("collection create item_count=0")

            dup = client.post(
                "/api/v1/collections",
                json={"name": "RC Browser Collection"},
            )
            assert_status("collection duplicate 409", dup, 409)

            same = client.patch(
                f"/api/v1/collections/{browser_col_id}",
                json={"name": "RC Browser Collection"},
            )
            if assert_status("collection rename no-op 200", same, 200):
                # no-op may keep updated_at; just ensure name unchanged
                if same.json()["name"] != "RC Browser Collection":
                    fail("noop name", same.json()["name"])
                else:
                    ok("noop rename keeps name")

            renamed = client.patch(
                f"/api/v1/collections/{browser_col_id}",
                json={"name": "RC Browser Collection Renamed"},
            )
            assert_status("collection rename 200", renamed, 200)

            conflict = client.patch(
                f"/api/v1/collections/{browser_col_id}",
                json={"name": "RC Rename Target"},
            )
            assert_status("collection rename conflict 409", conflict, 409)

            multi_del = client.delete(f"/api/v1/collections/{ids['multi']}")
            assert_status("non-empty collection DELETE 409", multi_del, 409)

            empty_del = client.delete(f"/api/v1/collections/{ids['empty']}")
            if assert_status("empty collection DELETE 204", empty_del, 204):
                if empty_del.content:
                    fail("empty delete body", repr(empty_del.content))
                else:
                    ok("empty delete body length 0")

            print("RC-1 Item create / update / link")
            post_item = client.post(
                "/api/v1/items",
                json={
                    "title": "RC Browser Item",
                    "category_id": str(ids["movie"]),
                    "collection_id": None,
                    "status": "PLANNED",
                    "rating": 0,
                    "progress_note": None,
                    "memo": None,
                },
            )
            if not assert_status("item POST 201", post_item, 201):
                return 1
            browser_item_id = post_item.json()["id"]

            in_col = client.post(
                "/api/v1/items",
                json={
                    "title": "RC In Collection Item",
                    "category_id": str(ids["movie"]),
                    "collection_id": browser_col_id,
                    "status": "PLANNED",
                    "rating": 0,
                },
            )
            assert_status("item POST into collection 201", in_col, 201)
            in_col_id = in_col.json()["id"]
            col_after = client.get(f"/api/v1/collections/{browser_col_id}").json()
            if col_after["item_count"] != 1:
                fail("collection item_count after create", str(col_after["item_count"]))
            else:
                ok("collection item_count=1 after create")

            before = client.get(f"/api/v1/items/{browser_item_id}").json()["updated_at"]
            noop2 = client.patch(
                f"/api/v1/items/{browser_item_id}",
                json={"title": "RC Browser Item"},
            )
            if assert_status("item identical PATCH 200", noop2, 200):
                if noop2.json()["updated_at"] != before:
                    fail("item noop updated_at", "changed on identical title")
                else:
                    ok("item noop updated_at stable")

            patch = client.patch(
                f"/api/v1/items/{browser_item_id}",
                json={
                    "title": "RC Browser Item Updated",
                    "status": "COMPLETED",
                    "rating": 4.5,
                    "progress_note": "QA 완료",
                    "memo": "브라우저 QA\n두 번째 줄",
                },
            )
            if assert_status("item general PATCH 200", patch, 200):
                body = patch.json()
                if body["rating"] != 4.5 or body["status"] != "COMPLETED":
                    fail("item patch fields", str(body))
                else:
                    ok("item patch fields applied")

            cat_patch = client.patch(
                f"/api/v1/items/{browser_item_id}",
                json={"category_id": str(ids["drama"])},
            )
            assert_status("item category PATCH 200", cat_patch, 200)

            link = client.patch(
                f"/api/v1/items/{ids['standalone']}",
                json={"collection_id": str(ids["multi"])},
            )
            if assert_status("item link to multi 200", link, 200):
                multi = client.get(f"/api/v1/collections/{ids['multi']}").json()
                if multi["item_count"] != 3:
                    fail("multi count after link", str(multi["item_count"]))
                else:
                    ok("multi item_count=3 after link")

            move = client.patch(
                f"/api/v1/items/{ids['standalone']}",
                json={"collection_id": browser_col_id},
            )
            assert_status("item move collection 200", move, 200)
            multi_after_move = client.get(f"/api/v1/collections/{ids['multi']}").json()
            if multi_after_move["item_count"] != 2:
                fail("multi after move", str(multi_after_move["item_count"]))
            else:
                ok("multi kept after move")

            form_unlink = client.patch(
                f"/api/v1/items/{ids['standalone']}",
                json={"collection_id": None},
            )
            assert_status("form-style unlink 200", form_unlink, 200)
            assert_status(
                "browser col kept after form unlink path",
                client.get(f"/api/v1/collections/{browser_col_id}"),
                200,
            )

            print("RC-1 quick unlink / last unlink / status")
            unlink = client.patch(
                f"/api/v1/items/{ids['multi_planned']}",
                json={"collection_id": None},
            )
            if assert_status("quick unlink PATCH 200", unlink, 200):
                if unlink.json().get("collection") is not None:
                    fail("unlink collection", "expected null")
                else:
                    ok("unlink response collection null")
            assert_status(
                "unlinked item GET 200",
                client.get(f"/api/v1/items/{ids['multi_planned']}"),
                200,
            )
            assert_status(
                "multi kept after unlink",
                client.get(f"/api/v1/collections/{ids['multi']}"),
                200,
            )

            last_unlink = client.patch(
                f"/api/v1/items/{ids['single_item']}",
                json={"collection_id": None},
            )
            if assert_status("last item unlink 200", last_unlink, 200):
                single_col = client.get(f"/api/v1/collections/{ids['single']}")
                if assert_status("empty single collection kept", single_col, 200):
                    data = single_col.json()
                    if data["item_count"] != 0 or data.get("categories"):
                        fail(
                            "last unlink empty state",
                            f"count={data['item_count']} cats={data.get('categories')}",
                        )
                    else:
                        ok("last unlink item_count=0 categories=[]")

            status = client.patch(
                f"/api/v1/items/{ids['multi_completed']}",
                json={"status": "PLANNED"},
            )
            assert_status("quick status PATCH 200", status, 200)

            print("RC-1 delete policies")
            # Create a one-item collection then DELETE item → collection gone
            one = client.post("/api/v1/collections", json={"name": f"RC LastDelete {run_tag}"})
            one_id = one.json()["id"]
            one_item = client.post(
                "/api/v1/items",
                json={
                    "title": "RC Last Delete Item",
                    "category_id": str(ids["movie"]),
                    "collection_id": one_id,
                },
            )
            one_item_id = one_item.json()["id"]
            delete_last = client.delete(f"/api/v1/items/{one_item_id}")
            if assert_status("last item DELETE 204", delete_last, 204):
                if delete_last.content:
                    fail("item delete body", repr(delete_last.content))
                else:
                    ok("item delete body length 0")
            assert_status(
                "collection auto-deleted after last item DELETE",
                client.get(f"/api/v1/collections/{one_id}"),
                404,
            )

            # Contrast: empty collection after unlink is still deletable via DELETE
            assert_status(
                "empty single DELETE 204",
                client.delete(f"/api/v1/collections/{ids['single']}"),
                204,
            )

            print("RC-1 history / legacy / isolation")
            assert_status(
                "other user item 404",
                client.patch(
                    f"/api/v1/items/{ids['other_item']}",
                    json={"collection_id": None},
                ),
                404,
            )

            with session_factory() as verify_db:
                hi = verify_db.scalar(
                    select(RecommendationHistoryItem).where(
                        RecommendationHistoryItem.item_id == ids["history_item"]
                    )
                )
                if hi is None or hi.title_snapshot != "RC History Item":
                    fail("history snapshot", "missing or changed")
                else:
                    ok("history snapshot preserved")
                mapping = verify_db.scalar(
                    select(func.count())
                    .select_from(LegacyImportItem)
                    .where(LegacyImportItem.item_id == ids["legacy_item"])
                )
                if mapping != 1:
                    fail("legacy mapping", str(mapping))
                else:
                    ok("legacy mapping preserved")

            # History item status patch must not change snapshot
            client.patch(
                f"/api/v1/items/{ids['history_item']}",
                json={"status": "COMPLETED", "title": "RC History Item Renamed"},
            )
            with session_factory() as verify_db:
                hi = verify_db.scalar(
                    select(RecommendationHistoryItem).where(
                        RecommendationHistoryItem.item_id == ids["history_item"]
                    )
                )
                if (
                    hi is None
                    or hi.title_snapshot != "RC History Item"
                    or hi.status_at_selection != ItemStatus.PLANNED
                ):
                    fail("history immutable after PATCH", str(hi))
                else:
                    ok("history immutable after item PATCH")

        app.dependency_overrides.clear()

    print(f"\nResult: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
