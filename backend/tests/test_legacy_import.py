"""Tests for legacy movie.json import."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

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
from app.scripts.import_legacy_movies import main as import_main
from app.services.legacy.importer import (
    ImportBlockedError,
    ImportEnvironmentError,
    run_legacy_import,
)
from app.services.legacy.import_plan import build_import_plan
from app.services.legacy.import_reporter import IMPORT_REPORT_FILES
from app.services.legacy.selection import pick_duplicate_winner
from app.services.legacy.series_classifier import SeriesClassification
from app.services.legacy.transformer import convert_legacy_item
from app.services.seed import run_seed


def _base_item(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": 1,
        "category": {"id": 3, "name": "영화"},
        "name": "테스트 영화",
        "series": "",
        "haveSeen": False,
        "starNum": 3.5,
        "registDt": "2017-03-03T11:37:32+0900",
        "modifyDt": "2026-05-04T20:09:12+0900",
    }
    item.update(overrides)
    return item


@pytest.fixture
def seeded_user(db) -> User:
    result = run_seed(db)
    user = db.scalar(select(User).where(User.email == result["user_email"]))
    assert user is not None
    return user


def _write_movie(path: Path, payload: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_skip_missing_category(tmp_path: Path) -> None:
    payload = [_base_item(), _base_item(id=2, category=None, name="카테고리 없음")]
    path = tmp_path / "movie.json"
    _write_movie(path, payload)
    plan = build_import_plan(path)
    assert plan.skipped_missing_category_count == 1
    assert plan.imported_items_count == 1


def test_ambiguous_import_fields_cleared(tmp_path: Path) -> None:
    payload = [
        _base_item(id=1, series="???"),
    ]
    path = tmp_path / "movie.json"
    _write_movie(path, payload)
    plan = build_import_plan(path)
    assert plan.cleared_ambiguous_series_count == 1
    item = plan.to_import[0]
    assert item.collection_name is None
    assert item.progress_note is None
    assert item.cleared_ambiguous is True


def test_duplicate_title_keeps_one(tmp_path: Path) -> None:
    payload = [
        _base_item(id=1, name="동일제목", haveSeen=False, starNum=1.0),
        _base_item(id=2, name="동일제목", haveSeen=True, starNum=4.0),
    ]
    path = tmp_path / "movie.json"
    _write_movie(path, payload)
    plan = build_import_plan(path)
    assert plan.imported_items_count == 1
    assert plan.skipped_duplicate_titles_count == 1
    assert plan.to_import[0].source_id == 2


def test_duplicate_completed_priority() -> None:
    planned = convert_legacy_item(
        _base_item(id=1, haveSeen=False),
        source_index=0,
        frequency_map={},
        duplicate_ids=set(),
    )
    completed = convert_legacy_item(
        _base_item(id=2, haveSeen=True),
        source_index=1,
        frequency_map={},
        duplicate_ids=set(),
    )
    sel = pick_duplicate_winner([planned, completed])
    assert sel.kept.source_id == 2
    assert sel.selection_reason == "COMPLETED 상태 우선"


def test_duplicate_rating_priority() -> None:
    low = convert_legacy_item(
        _base_item(id=1, haveSeen=True, starNum=2.0),
        source_index=0,
        frequency_map={},
        duplicate_ids=set(),
    )
    high = convert_legacy_item(
        _base_item(id=2, haveSeen=True, starNum=4.5),
        source_index=1,
        frequency_map={},
        duplicate_ids=set(),
    )
    sel = pick_duplicate_winner([low, high])
    assert sel.kept.source_id == 2


def test_duplicate_updated_at_priority() -> None:
    older = convert_legacy_item(
        _base_item(id=1, modifyDt="2017-03-03T11:37:32+0900"),
        source_index=0,
        frequency_map={},
        duplicate_ids=set(),
    )
    newer = convert_legacy_item(
        _base_item(id=2, modifyDt="2026-05-04T20:09:12+0900"),
        source_index=1,
        frequency_map={},
        duplicate_ids=set(),
    )
    sel = pick_duplicate_winner([older, newer])
    assert sel.kept.source_id == 2


def test_duplicate_source_id_tiebreak() -> None:
    first = convert_legacy_item(
        _base_item(id=1),
        source_index=0,
        frequency_map={},
        duplicate_ids=set(),
    )
    second = convert_legacy_item(
        _base_item(id=2),
        source_index=1,
        frequency_map={},
        duplicate_ids=set(),
    )
    sel = pick_duplicate_winner([first, second])
    assert sel.kept.source_id == 2


def test_duplicate_does_not_merge_values(tmp_path: Path) -> None:
    payload = [
        _base_item(id=1, name="동일", haveSeen=False, starNum=1.0),
        _base_item(id=2, name="동일", haveSeen=True, starNum=5.0),
    ]
    path = tmp_path / "movie.json"
    _write_movie(path, payload)
    plan = build_import_plan(path)
    kept = plan.to_import[0]
    assert kept.source_id == 2
    assert kept.rating == 5.0
    assert kept.status == "COMPLETED"


def test_dry_run_no_db_changes(db, seeded_user, tmp_path: Path) -> None:
    before_items = db.scalar(select(func.count()).select_from(Item))
    before_collections = db.scalar(select(func.count()).select_from(Collection))
    path = tmp_path / "movie.json"
    _write_movie(path, [_base_item()])
    report_dir = tmp_path / "import"

    result = run_legacy_import(
        db,
        input_path=path,
        report_dir=report_dir,
        user_email=seeded_user.email,
        dry_run=True,
        apply=False,
        pretty=True,
    )
    db.rollback()

    assert result.summary["imported_items"] == 1
    assert db.scalar(select(func.count()).select_from(Item)) == before_items
    assert db.scalar(select(func.count()).select_from(Collection)) == before_collections
    assert {p.name for p in result.report_paths} == set(IMPORT_REPORT_FILES)


def test_apply_import_and_reports(db, seeded_user, tmp_path: Path) -> None:
    payload = [
        _base_item(id=10, name="영화 A", series="터미네이터"),
        _base_item(id=11, name="영화 B", series="터미네이터"),
        _base_item(id=12, name="영화 C", series="1~3"),
        _base_item(id=13, name="영화 D", series="???"),
        _base_item(id=14, category=None, name="skip me"),
    ]
    path = tmp_path / "movie.json"
    _write_movie(path, payload)
    report_dir = tmp_path / "import"

    result = run_legacy_import(
        db,
        input_path=path,
        report_dir=report_dir,
        user_email=seeded_user.email,
        dry_run=False,
        apply=True,
        pretty=True,
        commit=False,
    )

    assert result.summary["imported_items"] == 4
    assert result.summary["skipped_missing_category"] == 1
    assert result.verification["source_equation_valid"] is True

    items = db.scalars(select(Item).where(Item.user_id == seeded_user.id)).all()
    assert len(items) == 4

    ambiguous_row = db.scalar(
        select(LegacyImportItem).where(LegacyImportItem.source_id == 13)
    )
    assert ambiguous_row is not None
    ambiguous_item = db.get(Item, ambiguous_row.item_id)
    assert ambiguous_item is not None
    assert ambiguous_item.collection_id is None
    assert ambiguous_item.progress_note is None

    collections = db.scalars(select(Collection).where(Collection.user_id == seeded_user.id)).all()
    assert len(collections) == 1
    assert collections[0].name == "터미네이터"

    categories = db.scalar(select(func.count()).select_from(Category))
    assert categories == 10
    db.rollback()


def test_collection_not_duplicated(db, seeded_user, tmp_path: Path) -> None:
    existing = Collection(user_id=seeded_user.id, name="터미네이터")
    db.add(existing)
    db.flush()

    path = tmp_path / "movie.json"
    _write_movie(
        path,
        [
            _base_item(id=20, series="터미네이터"),
            _base_item(id=21, name="터미 2", series="터미네이터"),
        ],
    )
    run_legacy_import(
        db,
        input_path=path,
        report_dir=tmp_path / "import",
        user_email=seeded_user.email,
        apply=True,
        commit=False,
    )
    count = db.scalar(
        select(func.count()).select_from(Collection).where(Collection.user_id == seeded_user.id)
    )
    assert count == 1
    db.rollback()


def test_reimport_blocked(db, seeded_user, tmp_path: Path) -> None:
    path = tmp_path / "movie.json"
    _write_movie(path, [_base_item(id=30)])
    report_dir = tmp_path / "import"

    run_legacy_import(
        db,
        input_path=path,
        report_dir=report_dir,
        user_email=seeded_user.email,
        apply=True,
    )
    db.commit()

    with pytest.raises(ImportBlockedError):
        run_legacy_import(
            db,
            input_path=path,
            report_dir=report_dir,
            user_email=seeded_user.email,
            apply=True,
        )


def test_reset_imported_data_dev_only(db, seeded_user, tmp_path: Path) -> None:
    path = tmp_path / "movie.json"
    _write_movie(path, [_base_item(id=40)])
    report_dir = tmp_path / "import"

    run_legacy_import(
        db,
        input_path=path,
        report_dir=report_dir,
        user_email=seeded_user.email,
        apply=True,
    )
    db.commit()

    with patch("app.services.legacy.importer.get_settings") as mock_settings:
        mock_settings.return_value.app_env = "production"
        with pytest.raises(ImportEnvironmentError):
            run_legacy_import(
                db,
                input_path=path,
                report_dir=report_dir,
                user_email=seeded_user.email,
                apply=True,
                reset_imported_data_flag=True,
            )

    run_legacy_import(
        db,
        input_path=path,
        report_dir=report_dir,
        user_email=seeded_user.email,
        apply=True,
        reset_imported_data_flag=True,
    )
    db.commit()

    runs = db.scalars(
        select(LegacyImportRun).where(
            LegacyImportRun.user_id == seeded_user.id,
            LegacyImportRun.status == LegacyImportRunStatus.SUCCESS,
        )
    ).all()
    assert len(runs) == 1
    assert db.scalar(select(func.count()).select_from(Item).where(Item.user_id == seeded_user.id)) == 1


def test_transaction_rollback_on_error(db, seeded_user, tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "movie.json"
    _write_movie(path, [_base_item(id=50)])
    report_dir = tmp_path / "import"

    def boom(*args, **kwargs):
        raise RuntimeError("forced failure")

    monkeypatch.setattr(
        "app.services.legacy.importer.write_import_reports",
        boom,
    )

    before = db.scalar(select(func.count()).select_from(Item))
    with pytest.raises(RuntimeError):
        run_legacy_import(
            db,
            input_path=path,
            report_dir=report_dir,
            user_email=seeded_user.email,
            apply=True,
            commit=False,
        )
    db.rollback()
    assert db.scalar(select(func.count()).select_from(Item)) == before
    assert (
        db.scalar(
            select(func.count()).select_from(LegacyImportRun).where(
                LegacyImportRun.status == LegacyImportRunStatus.SUCCESS
            )
        )
        == 0
    )


def test_cli_requires_mode(tmp_path: Path) -> None:
    path = tmp_path / "movie.json"
    _write_movie(path, [_base_item()])
    with pytest.raises(SystemExit) as exc:
        import_main(["--input", str(path), "--report-dir", str(tmp_path / "out")])
    assert exc.value.code != 0


def test_progress_note_stored(db, seeded_user, tmp_path: Path) -> None:
    path = tmp_path / "movie.json"
    _write_movie(path, [_base_item(id=60, series="1~3, 5")])
    run_legacy_import(
        db,
        input_path=path,
        report_dir=tmp_path / "import",
        user_email=seeded_user.email,
        apply=True,
        commit=False,
    )
    item = db.scalar(select(Item).where(Item.user_id == seeded_user.id))
    assert item is not None
    assert item.progress_note == "1~3, 5"
    assert item.collection_id is None
    db.rollback()


def _legacy_movie_path() -> Path:
    candidates = [
        Path("/app/legacy-data/movie.json"),
        Path(__file__).resolve().parents[2] / "legacy-data" / "movie.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[-1]


@pytest.mark.skipif(
    not _legacy_movie_path().is_file(),
    reason="legacy-data/movie.json not present",
)
def test_full_file_dry_run_counts(db, seeded_user, tmp_path: Path) -> None:
    report_dir = tmp_path / "import"
    result = run_legacy_import(
        db,
        input_path=_legacy_movie_path(),
        report_dir=report_dir,
        user_email=seeded_user.email,
        dry_run=True,
        pretty=True,
    )
    assert result.summary["source_total"] == 7213
    assert result.summary["imported_items"] == 7202
    assert result.summary["skipped_missing_category"] == 6
    assert result.summary["skipped_duplicate_titles"] == 5
    assert result.summary["cleared_ambiguous_series"] == 11
    assert result.verification["source_equation_valid"] is True


@pytest.mark.skipif(
    not _legacy_movie_path().is_file(),
    reason="legacy-data/movie.json not present",
)
def test_full_file_apply(db, seeded_user, tmp_path: Path) -> None:
    report_dir = tmp_path / "import"
    existing = db.scalar(
        select(LegacyImportRun).where(
            LegacyImportRun.user_id == seeded_user.id,
            LegacyImportRun.status == LegacyImportRunStatus.SUCCESS,
        )
    )
    kwargs: dict[str, object] = {
        "input_path": _legacy_movie_path(),
        "report_dir": report_dir,
        "user_email": seeded_user.email,
        "apply": True,
    }
    if existing is not None:
        kwargs["reset_imported_data_flag"] = True

    result = run_legacy_import(db, **kwargs)  # type: ignore[arg-type]

    count = db.scalar(select(func.count()).select_from(Item).where(Item.user_id == seeded_user.id))
    assert count == 7202
    assert result.verification["source_equation_valid"] is True
