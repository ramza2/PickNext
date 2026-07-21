"""Tests for legacy import in-place repairs."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import func, inspect, select, text

from app.models import (
    Category,
    Collection,
    Item,
    ItemStatus,
    LegacyImportDisposition,
    LegacyImportItem,
    LegacyImportRun,
    LegacyImportRunStatus,
    User,
)
from app.scripts.repair_legacy_import_data import main as repair_main
from app.services.legacy.import_plan import TITLE_REPAIR_SOURCE_ID
from app.services.legacy.repair import RepairBlockedError, run_legacy_import_repair
from app.services.legacy.repair_reporter import REPAIR_REPORT_FILES
from app.services.seed import run_seed


LONG_TITLE = "픽사" + "A" * 310


def _write_movie(path: Path, payload: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def seeded_user(db) -> User:
    result = run_seed(db)
    user = db.scalar(select(User).where(User.email == result["user_email"]))
    assert user is not None
    return user


@pytest.fixture
def import_run_with_items(db, seeded_user) -> tuple[LegacyImportRun, dict[str, Item]]:
    categories = {
        c.name: c
        for c in db.scalars(select(Category).where(Category.user_id == seeded_user.id))
    }
    run = LegacyImportRun(
        user_id=seeded_user.id,
        source_filename="movie.json",
        source_sha256="test-sha",
        source_total_count=5,
        imported_item_count=5,
        skipped_count=0,
        status=LegacyImportRunStatus.SUCCESS,
    )
    db.add(run)
    db.flush()

    items: dict[str, Item] = {}
    specs = [
        ("title", TITLE_REPAIR_SOURCE_ID, "영화", LONG_TITLE[:300], None, None),
        ("bond", 100, "영화", "007 영화1", None, "007 시리즈"),
        ("bond2", 101, "영화", "007 영화2", None, "007 시리즈"),
        ("47m", 102, "영화", "47미터 상어", None, "47미터"),
        ("28d", 103, "영화", "28일 후", None, "28일 후"),
    ]
    for key, source_id, cat_name, title, collection_id, progress_note in specs:
        item = Item(
            user_id=seeded_user.id,
            category_id=categories[cat_name].id,
            collection_id=collection_id,
            title=title,
            status=ItemStatus.PLANNED,
            rating=Decimal("3.0"),
            progress_note=progress_note,
            created_at=db.scalar(text("SELECT now()")),
            updated_at=db.scalar(text("SELECT now()")),
        )
        db.add(item)
        db.flush()
        db.add(
            LegacyImportItem(
                import_run_id=run.id,
                item_id=item.id,
                source_id=source_id,
                disposition=LegacyImportDisposition.IMPORTED,
            )
        )
        items[key] = item

    db.flush()
    return run, items


def test_items_title_column_is_text(db) -> None:
    inspector = inspect(db.bind)
    columns = {col["name"]: col for col in inspector.get_columns("items")}
    assert "TEXT" in str(columns["title"]["type"]).upper()


def test_long_title_can_be_saved(db, seeded_user) -> None:
    category = db.scalar(
        select(Category).where(Category.user_id == seeded_user.id, Category.name == "영화")
    )
    item = Item(
        user_id=seeded_user.id,
        category_id=category.id,
        title=LONG_TITLE,
        status=ItemStatus.PLANNED,
        rating=Decimal("0.0"),
    )
    db.add(item)
    db.flush()
    assert len(item.title) > 300
    db.rollback()


def test_title_repair_from_movie_json(
    db, seeded_user, import_run_with_items, tmp_path: Path
) -> None:
    run, items = import_run_with_items
    movie_path = tmp_path / "movie.json"
    _write_movie(
        movie_path,
        [
            {
                "id": TITLE_REPAIR_SOURCE_ID,
                "name": LONG_TITLE,
                "category": {"id": 3, "name": "영화"},
                "haveSeen": False,
                "starNum": 0.0,
                "registDt": "2017-03-03T11:37:32+0900",
            }
        ],
    )

    result = run_legacy_import_repair(
        db,
        movie_path=movie_path,
        report_dir=tmp_path / "repair",
        user_email=seeded_user.email,
        import_run_id=run.id,
        apply=True,
        commit=False,
        pretty=True,
    )

    item = db.get(Item, items["title"].id)
    assert item is not None
    assert item.title == LONG_TITLE
    assert result.title_repair["new_length"] > 300
    assert result.verification["db_item_count_unchanged"] is True
    db.rollback()


def test_required_collection_repairs(
    db, seeded_user, import_run_with_items, tmp_path: Path
) -> None:
    run, items = import_run_with_items
    movie_path = tmp_path / "movie.json"
    _write_movie(
        movie_path,
        [{"id": TITLE_REPAIR_SOURCE_ID, "name": LONG_TITLE, "category": {"id": 3}}],
    )

    run_legacy_import_repair(
        db,
        movie_path=movie_path,
        report_dir=tmp_path / "repair",
        user_email=seeded_user.email,
        import_run_id=run.id,
        apply=True,
        commit=False,
    )

    import_item_ids = {item.id for item in items.values()}
    notes_in_fixture = {item.progress_note for item in items.values() if item.progress_note}

    for note in notes_in_fixture:
        remaining = db.scalar(
            select(func.count())
            .select_from(Item)
            .where(Item.id.in_(import_item_ids), Item.progress_note == note)
        )
        assert remaining == 0

    bond = db.get(Item, items["bond"].id)
    assert bond is not None
    assert bond.progress_note is None
    assert bond.collection_id is not None
    collection = db.get(Collection, bond.collection_id)
    assert collection is not None
    assert collection.name == "007 시리즈"

    for note in notes_in_fixture:
        linked = db.scalar(
            select(func.count())
            .select_from(Item)
            .where(
                Item.id.in_(import_item_ids),
                Item.collection_id.is_not(None),
            )
            .join(Collection, Collection.id == Item.collection_id)
            .where(Collection.name == note)
        )
        assert linked >= 1
    db.rollback()


def test_reuses_existing_collection(
    db, seeded_user, import_run_with_items, tmp_path: Path
) -> None:
    run, items = import_run_with_items
    existing = db.scalar(
        select(Collection).where(
            Collection.user_id == seeded_user.id,
            Collection.name == "007 시리즈",
        )
    )
    if existing is None:
        existing = Collection(user_id=seeded_user.id, name="007 시리즈")
        db.add(existing)
        db.flush()

    movie_path = tmp_path / "movie.json"
    _write_movie(movie_path, [{"id": TITLE_REPAIR_SOURCE_ID, "name": LONG_TITLE}])

    run_legacy_import_repair(
        db,
        movie_path=movie_path,
        report_dir=tmp_path / "repair",
        user_email=seeded_user.email,
        import_run_id=run.id,
        apply=True,
        commit=False,
    )

    count = db.scalar(
        select(func.count())
        .select_from(Collection)
        .where(Collection.user_id == seeded_user.id, Collection.name == "007 시리즈")
    )
    assert count == 1
    bond = db.get(Item, items["bond"].id)
    assert bond.collection_id == existing.id
    db.rollback()


def test_dry_run_no_changes(
    db, seeded_user, import_run_with_items, tmp_path: Path
) -> None:
    run, items = import_run_with_items
    before_title = items["title"].title
    movie_path = tmp_path / "movie.json"
    _write_movie(movie_path, [{"id": TITLE_REPAIR_SOURCE_ID, "name": LONG_TITLE}])

    result = run_legacy_import_repair(
        db,
        movie_path=movie_path,
        report_dir=tmp_path / "repair",
        user_email=seeded_user.email,
        import_run_id=run.id,
        dry_run=True,
        pretty=True,
    )

    item = db.get(Item, items["title"].id)
    assert item.title == before_title
    assert {p.name for p in result.report_paths} == set(REPAIR_REPORT_FILES)
    db.rollback()


def test_idempotent_second_run(
    db, seeded_user, import_run_with_items, tmp_path: Path
) -> None:
    run, _ = import_run_with_items
    movie_path = tmp_path / "movie.json"
    _write_movie(movie_path, [{"id": TITLE_REPAIR_SOURCE_ID, "name": LONG_TITLE}])
    report_dir = tmp_path / "repair"

    run_legacy_import_repair(
        db,
        movie_path=movie_path,
        report_dir=report_dir,
        user_email=seeded_user.email,
        import_run_id=run.id,
        apply=True,
        commit=False,
    )
    second = run_legacy_import_repair(
        db,
        movie_path=movie_path,
        report_dir=report_dir,
        user_email=seeded_user.email,
        import_run_id=run.id,
        apply=True,
        commit=False,
    )
    assert second.summary["title_repairs_applied"] == 0
    assert second.summary["collection_items_updated"] == 0
    assert second.summary["collection_names_created"] == 0
    db.rollback()


def test_wrong_import_run_blocked(db, seeded_user, tmp_path: Path) -> None:
    other_run = LegacyImportRun(
        user_id=seeded_user.id,
        source_filename="movie.json",
        source_sha256="other",
        source_total_count=0,
        status=LegacyImportRunStatus.SUCCESS,
    )
    db.add(other_run)
    db.flush()
    movie_path = tmp_path / "movie.json"
    _write_movie(movie_path, [{"id": 1, "name": "x"}])

    with pytest.raises(RepairBlockedError):
        run_legacy_import_repair(
            db,
            movie_path=movie_path,
            report_dir=tmp_path / "repair",
            user_email=seeded_user.email,
            import_run_id=other_run.id,
            dry_run=True,
        )
    db.rollback()


def test_missing_source_title_aborts(
    db, seeded_user, import_run_with_items, tmp_path: Path
) -> None:
    run, _ = import_run_with_items
    movie_path = tmp_path / "movie.json"
    _write_movie(movie_path, [{"id": 999, "name": "other"}])

    with pytest.raises(RepairBlockedError):
        run_legacy_import_repair(
            db,
            movie_path=movie_path,
            report_dir=tmp_path / "repair",
            user_email=seeded_user.email,
            import_run_id=run.id,
            dry_run=True,
        )
    db.rollback()


def test_cli_requires_mode(tmp_path: Path) -> None:
    path = tmp_path / "movie.json"
    _write_movie(path, [{"id": 1, "name": "x"}])
    with pytest.raises(SystemExit):
        repair_main(["--input", str(path), "--report-dir", str(tmp_path / "out")])


def test_additional_candidates_not_auto_applied(
    db, seeded_user, import_run_with_items, tmp_path: Path
) -> None:
    run, items = import_run_with_items
    category = db.scalar(
        select(Category).where(Category.user_id == seeded_user.id, Category.name == "영화")
    )
    extra = Item(
        user_id=seeded_user.id,
        category_id=category.id,
        title="후보1",
        status=ItemStatus.PLANNED,
        rating=Decimal("1.0"),
        progress_note="테스트후보노트-반복",
    )
    extra2 = Item(
        user_id=seeded_user.id,
        category_id=category.id,
        title="후보2",
        status=ItemStatus.PLANNED,
        rating=Decimal("1.0"),
        progress_note="테스트후보노트-반복",
    )
    db.add(extra)
    db.add(extra2)
    db.flush()
    db.add(
        LegacyImportItem(
            import_run_id=run.id,
            item_id=extra.id,
            source_id=9001,
            disposition=LegacyImportDisposition.IMPORTED,
        )
    )
    db.add(
        LegacyImportItem(
            import_run_id=run.id,
            item_id=extra2.id,
            source_id=9002,
            disposition=LegacyImportDisposition.IMPORTED,
        )
    )
    db.flush()

    movie_path = tmp_path / "movie.json"
    _write_movie(movie_path, [{"id": TITLE_REPAIR_SOURCE_ID, "name": LONG_TITLE}])

    result = run_legacy_import_repair(
        db,
        movie_path=movie_path,
        report_dir=tmp_path / "repair",
        user_email=seeded_user.email,
        import_run_id=run.id,
        dry_run=True,
    )

    candidate_notes = {row["progress_note"] for row in result.additional_candidates}
    assert "테스트후보노트-반복" in candidate_notes
    assert db.get(Item, extra.id).progress_note == "테스트후보노트-반복"
    db.rollback()


def test_counts_unchanged(
    db, seeded_user, import_run_with_items, tmp_path: Path
) -> None:
    run, _ = import_run_with_items
    before_items = db.scalar(select(func.count()).select_from(Item))
    before_planned = db.scalar(
        select(func.count()).select_from(Item).where(Item.status == ItemStatus.PLANNED)
    )
    movie_path = tmp_path / "movie.json"
    _write_movie(movie_path, [{"id": TITLE_REPAIR_SOURCE_ID, "name": LONG_TITLE}])

    result = run_legacy_import_repair(
        db,
        movie_path=movie_path,
        report_dir=tmp_path / "repair",
        user_email=seeded_user.email,
        import_run_id=run.id,
        apply=True,
        commit=False,
    )

    assert db.scalar(select(func.count()).select_from(Item)) == before_items
    assert (
        db.scalar(select(func.count()).select_from(Item).where(Item.status == ItemStatus.PLANNED))
        == before_planned
    )
    assert result.verification["planned_count_unchanged"] is True
    db.rollback()


def test_reports_preserved_per_run(
    db, seeded_user, import_run_with_items, tmp_path: Path
) -> None:
    run, _ = import_run_with_items
    movie_path = tmp_path / "movie.json"
    _write_movie(movie_path, [{"id": TITLE_REPAIR_SOURCE_ID, "name": LONG_TITLE}])
    report_dir = tmp_path / "repair"

    first = run_legacy_import_repair(
        db,
        movie_path=movie_path,
        report_dir=report_dir,
        user_email=seeded_user.email,
        import_run_id=run.id,
        dry_run=True,
    )
    second = run_legacy_import_repair(
        db,
        movie_path=movie_path,
        report_dir=report_dir,
        user_email=seeded_user.email,
        import_run_id=run.id,
        dry_run=True,
    )

    first_dir = first.report_paths[0].parent
    second_dir = second.report_paths[0].parent
    assert first_dir != second_dir
    assert first_dir.parent.name == "runs"
    assert (first_dir / "repair-summary.json").is_file()
    assert (second_dir / "repair-summary.json").is_file()
    db.rollback()
