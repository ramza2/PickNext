"""Legacy import must preserve Progress Notes longer than 200 characters."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.legacy.import_plan import build_import_plan
from app.services.legacy.series_classifier import SeriesClassification


def _base_item(**overrides):
    item = {
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


def test_legacy_import_plan_keeps_long_progress_note(tmp_path: Path) -> None:
    # Digit/range-heavy series classifies as PROGRESS_NOTE.
    full_note = ", ".join(f"{i}~{i+1}" for i in range(1, 80))
    assert len(full_note) > 200

    path = tmp_path / "movie.json"
    path.write_text(
        json.dumps([_base_item(id=18, name="아는 형님", series=full_note)], ensure_ascii=False),
        encoding="utf-8",
    )
    plan = build_import_plan(path)
    assert plan.imported_items_count == 1
    planned = plan.to_import[0]
    assert planned.progress_note == full_note
    assert planned.progress_note_truncated is False
    assert planned.collection_name is None


def test_long_series_still_classified_as_progress_note(tmp_path: Path) -> None:
    full_note = "1~10, " * 40
    assert len(full_note.strip()) > 200
    path = tmp_path / "movie.json"
    path.write_text(
        json.dumps([_base_item(id=7, series=full_note)], ensure_ascii=False),
        encoding="utf-8",
    )
    plan = build_import_plan(path)
    assert plan.to_import[0].progress_note is not None
    # Ensure classification path still treats it as progress note, not collection.
    from app.services.legacy.transformer import convert_legacy_item
    from app.services.legacy.series_classifier import build_series_frequency

    raw = json.loads(path.read_text(encoding="utf-8"))[0]
    conv = convert_legacy_item(
        raw,
        source_index=0,
        frequency_map=build_series_frequency([full_note]),
        duplicate_ids=set(),
    )
    assert conv.classification is not None
    assert conv.classification.result == SeriesClassification.PROGRESS_NOTE
