"""Unit tests for legacy movie.json dry-run analysis (no Import)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select, text

from app.models import Item, User
from app.scripts.analyze_legacy_movies import main as analyze_main
from app.services.legacy.analyzer import analyze_legacy_movies
from app.services.legacy.category_map import map_legacy_category_id
from app.services.legacy.dates import parse_legacy_datetime, to_utc_iso_z
from app.services.legacy.reporter import REPORT_FILES, write_reports
from app.services.legacy.series_classifier import (
    SeriesClassification,
    build_series_frequency,
    classify_series,
)
from app.services.legacy.transformer import convert_legacy_item


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


def test_convert_normal_item() -> None:
    raw = _base_item()
    result = convert_legacy_item(
        raw, source_index=0, frequency_map={}, duplicate_ids=set()
    )
    assert result.is_convertible
    assert result.title == "테스트 영화"
    assert result.category_name == "영화"
    assert result.status == "PLANNED"
    assert result.rating == 3.5
    assert result.created_at.endswith("Z")
    assert result.updated_at.endswith("Z")


def test_have_seen_status_conversion() -> None:
    planned = convert_legacy_item(
        _base_item(haveSeen=False),
        source_index=0,
        frequency_map={},
        duplicate_ids=set(),
    )
    completed = convert_legacy_item(
        _base_item(haveSeen=True, id=2),
        source_index=1,
        frequency_map={},
        duplicate_ids=set(),
    )
    assert planned.status == "PLANNED"
    assert completed.status == "COMPLETED"


def test_modify_dt_missing_uses_created_at() -> None:
    raw = _base_item()
    del raw["modifyDt"]
    result = convert_legacy_item(
        raw, source_index=0, frequency_map={}, duplicate_ids=set()
    )
    assert result.is_convertible
    assert result.updated_at == result.created_at


def test_rating_bounds_0_and_5() -> None:
    zero = convert_legacy_item(
        _base_item(starNum=0.0),
        source_index=0,
        frequency_map={},
        duplicate_ids=set(),
    )
    five = convert_legacy_item(
        _base_item(starNum=5.0, id=2),
        source_index=1,
        frequency_map={},
        duplicate_ids=set(),
    )
    assert zero.is_convertible and zero.rating == 0.0
    assert five.is_convertible and five.rating == 5.0


def test_rating_out_of_range() -> None:
    result = convert_legacy_item(
        _base_item(starNum=5.5),
        source_index=0,
        frequency_map={},
        duplicate_ids=set(),
    )
    assert not result.is_convertible
    assert "RATING_OUT_OF_RANGE" in result.error_codes


def test_category_mapping() -> None:
    assert map_legacy_category_id(1).name == "애니메이션"  # type: ignore[union-attr]
    assert map_legacy_category_id(10).name == "음식"  # type: ignore[union-attr]
    mapped = convert_legacy_item(
        _base_item(category={"id": 9, "name": "만화책"}),
        source_index=0,
        frequency_map={},
        duplicate_ids=set(),
    )
    assert mapped.category_name == "만화책"


def test_category_missing_and_mapping_failed() -> None:
    missing = convert_legacy_item(
        _base_item(category=None),
        source_index=0,
        frequency_map={},
        duplicate_ids=set(),
    )
    assert "MISSING_CATEGORY" in missing.error_codes

    failed = convert_legacy_item(
        _base_item(category={"id": 99, "name": "알수없음"}),
        source_index=1,
        frequency_map={},
        duplicate_ids=set(),
    )
    assert "CATEGORY_MAPPING_FAILED" in failed.error_codes


def test_date_parsing() -> None:
    dt = parse_legacy_datetime("2017-03-03T11:37:32+0900")
    assert to_utc_iso_z(dt) == "2017-03-03T02:37:32Z"


def test_duplicate_source_ids_and_titles(tmp_path: Path) -> None:
    payload = [
        _base_item(id=10, name="동일제목"),
        _base_item(id=10, name="다른제목"),
        _base_item(id=11, name="동일제목"),
    ]
    path = tmp_path / "movies.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    result = analyze_legacy_movies(path)
    assert result.summary.duplicate_source_ids == 2
    assert "10" in result.duplicate_source_ids
    assert result.summary.warnings >= 2
    assert any(row.title == "동일제목" for row in result.duplicate_titles)


def test_collection_candidate_classification() -> None:
    freq = build_series_frequency(["터미네이터", "터미네이터", "터미네이터"])
    result = classify_series("터미네이터", category_id=3, frequency_map=freq)
    assert result.result == SeriesClassification.COLLECTION
    assert result.suggested_collection_name == "터미네이터"
    assert result.original_series == "터미네이터"


def test_progress_note_candidate_classification() -> None:
    series = "44~45, 57~58, 70, 155"
    freq = build_series_frequency([series])
    result = classify_series(series, category_id=3, frequency_map=freq)
    assert result.result == SeriesClassification.PROGRESS_NOTE
    assert result.suggested_progress_note == series
    assert result.original_series == series


def test_ambiguous_classification() -> None:
    freq = build_series_frequency(["???"])
    result = classify_series("???", category_id=3, frequency_map=freq)
    assert result.result == SeriesClassification.AMBIGUOUS


def test_entertainment_episode_classification() -> None:
    series = "1~2, 8, 212~214, 230"
    freq = build_series_frequency([series])
    result = classify_series(series, category_id=8, frequency_map=freq)
    assert result.result == SeriesClassification.PROGRESS_NOTE
    assert "예능" in result.reason or "숫자" in result.reason or "회차" in result.reason


def test_repeated_short_number_is_progress_not_collection() -> None:
    freq = build_series_frequency(["1"] * 14)
    result = classify_series("1", category_id=3, frequency_map=freq)
    assert result.result == SeriesClassification.PROGRESS_NOTE


def test_report_files_created(tmp_path: Path) -> None:
    payload = [
        _base_item(id=1, series="토이 스토리"),
        _base_item(id=2, name="토이 스토리 2", series="토이 스토리"),
        _base_item(id=3, series="1~3, 5"),
    ]
    input_path = tmp_path / "movie.json"
    input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    report_dir = tmp_path / "migration-report"

    result = analyze_legacy_movies(input_path)
    written = write_reports(result, report_dir, pretty=True)
    names = {path.name for path in written}
    assert names == set(REPORT_FILES)
    for name in REPORT_FILES:
        assert (report_dir / name).is_file()


def test_cli_dry_run(tmp_path: Path) -> None:
    payload = [_base_item()]
    input_path = tmp_path / "movie.json"
    input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    report_dir = tmp_path / "out"
    code = analyze_main(
        [
            "--input",
            str(input_path),
            "--report-dir",
            str(report_dir),
            "--pretty",
        ]
    )
    assert code == 0
    assert (report_dir / "summary.json").is_file()


def test_dry_run_does_not_touch_db_modules(tmp_path: Path) -> None:
    """Dry-run must not import or use the DB session layer."""
    import app.services.legacy.analyzer as analyzer_mod
    import app.services.legacy.reporter as reporter_mod
    import app.services.legacy.transformer as transformer_mod

    for module in (analyzer_mod, reporter_mod, transformer_mod):
        assert "app.db" not in getattr(module, "__dict__", {})
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "SessionLocal" not in source
        assert "get_db" not in source
        assert "create_engine" not in source

    payload = [_base_item(id=9999, name="DB변경금지")]
    input_path = tmp_path / "movie.json"
    input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    report_dir = tmp_path / "reports"

    result = analyze_legacy_movies(input_path)
    write_reports(result, report_dir)
    assert result.summary.convertible == 1
    assert (report_dir / "summary.json").is_file()


def test_dry_run_does_not_change_db(db, tmp_path: Path) -> None:
    before_users = db.scalar(select(func.count()).select_from(User))
    before_items = db.scalar(select(func.count()).select_from(Item))

    payload = [_base_item(id=9999, name="DB변경금지")]
    input_path = tmp_path / "movie.json"
    input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    report_dir = tmp_path / "reports"

    result = analyze_legacy_movies(input_path)
    write_reports(result, report_dir)

    after_users = db.scalar(select(func.count()).select_from(User))
    after_items = db.scalar(select(func.count()).select_from(Item))
    assert after_users == before_users
    assert after_items == before_items
    db.execute(text("SELECT 1"))


def test_original_series_preserved_with_whitespace() -> None:
    raw_series = "  터미네이터  "
    freq = build_series_frequency([raw_series.strip(), raw_series.strip()])
    result = classify_series(raw_series, category_id=3, frequency_map=freq)
    assert result.original_series == raw_series


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
def test_full_movie_json_integration(tmp_path: Path) -> None:
    result = analyze_legacy_movies(_legacy_movie_path())
    assert result.summary.total_read > 0
    assert (
        result.summary.convertible + result.summary.critical_errors
        <= result.summary.total_read
    )
    # Classification buckets cover convertible + invalid objects with series class
    classified = (
        result.summary.collection_candidates
        + result.summary.progress_note_candidates
        + result.summary.ambiguous
        + result.summary.empty_series
    )
    assert classified == result.summary.valid_json_objects

    report_dir = tmp_path / "full-report"
    write_reports(result, report_dir)
    summary = json.loads((report_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["total_read"] == result.summary.total_read
