"""Build legacy import plan from converted records."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.services.legacy.analyzer import load_json_array
from app.services.legacy.dates import parse_legacy_datetime
from app.services.legacy.selection import (
    DuplicateSelection,
    pick_duplicate_winner,
    record_summary,
)
from app.services.legacy.series_classifier import (
    SeriesClassification,
    build_series_frequency,
)
from app.services.legacy.transformer import ItemConversion, convert_legacy_item


TITLE_REPAIR_SOURCE_ID = 2209
PROGRESS_NOTE_MAX = 200

REQUIRED_COLLECTION_PROGRESS_NOTES: tuple[str, ...] = (
    "007 시리즈",
    "47미터",
    "28일 후",
    "007 북경특급",
    "99.9~형사 전문 변호사~",
)

ENTERTAINMENT_CATEGORY_NAME = "예능"


@dataclass
class PlannedImportItem:
    source_id: int
    source_index: int
    category_name: str
    category_legacy_id: int
    title: str
    status: str
    rating: float
    created_at: datetime
    updated_at: datetime
    collection_name: str | None
    progress_note: str | None
    cleared_ambiguous: bool
    progress_note_truncated: bool = False


@dataclass
class SkippedMissingCategory:
    source_id: int | None
    source_index: int
    title: str | None
    disposition: str = "SKIPPED_MISSING_CATEGORY"
    original_data: object = None


@dataclass
class ImportPlan:
    source_path: Path
    source_filename: str
    source_sha256: str
    source_total: int
    skipped_missing_category: list[SkippedMissingCategory] = field(default_factory=list)
    skipped_duplicate_titles: list[DuplicateSelection] = field(default_factory=list)
    cleared_ambiguous_series: list[PlannedImportItem] = field(default_factory=list)
    to_import: list[PlannedImportItem] = field(default_factory=list)
    invalid_items: list[ItemConversion] = field(default_factory=list)

    @property
    def eligible_after_validation(self) -> int:
        return self.source_total - len(self.skipped_missing_category) - len(self.invalid_items)

    @property
    def imported_items_count(self) -> int:
        return len(self.to_import)

    @property
    def skipped_missing_category_count(self) -> int:
        return len(self.skipped_missing_category)

    @property
    def skipped_duplicate_titles_count(self) -> int:
        return sum(len(sel.skipped) for sel in self.skipped_duplicate_titles)

    @property
    def cleared_ambiguous_series_count(self) -> int:
        return len(self.cleared_ambiguous_series)


def compute_file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _find_duplicate_ids(items: list[object]) -> set[int]:
    seen: set[int] = set()
    duplicates: set[int] = set()
    for raw in items:
        if not isinstance(raw, dict):
            continue
        raw_id = raw.get("id")
        if isinstance(raw_id, int) and not isinstance(raw_id, bool):
            if raw_id in seen:
                duplicates.add(raw_id)
            else:
                seen.add(raw_id)
    return duplicates


def _iso_to_datetime(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def _map_import_fields(conv: ItemConversion) -> tuple[str | None, str | None, bool]:
    classification = conv.classification
    if classification is None:
        return None, None, False

    if classification.result == SeriesClassification.AMBIGUOUS:
        return None, None, True

    if classification.result == SeriesClassification.COLLECTION:
        return classification.suggested_collection_name, None, False

    if classification.result == SeriesClassification.PROGRESS_NOTE:
        note = classification.suggested_progress_note
        truncated = False
        if note and len(note) > PROGRESS_NOTE_MAX:
            note = note[:PROGRESS_NOTE_MAX]
            truncated = True
        return None, note, False

    return None, None, False


def _to_planned(conv: ItemConversion) -> PlannedImportItem:
    assert conv.source_id is not None
    assert conv.category_name is not None
    assert conv.category_id is not None
    assert conv.title is not None
    assert conv.status is not None
    assert conv.rating is not None
    assert conv.created_at is not None
    assert conv.updated_at is not None

    collection_name, progress_note, cleared_ambiguous = _map_import_fields(conv)
    truncated = False
    if progress_note and len(progress_note) > PROGRESS_NOTE_MAX:
        progress_note = progress_note[:PROGRESS_NOTE_MAX]
        truncated = True

    title = conv.title

    return PlannedImportItem(
        source_id=conv.source_id,
        source_index=conv.source_index,
        category_name=conv.category_name,
        category_legacy_id=conv.category_id,
        title=title,
        status=conv.status,
        rating=conv.rating,
        created_at=_iso_to_datetime(conv.created_at),
        updated_at=_iso_to_datetime(conv.updated_at),
        collection_name=collection_name,
        progress_note=progress_note,
        cleared_ambiguous=cleared_ambiguous,
        progress_note_truncated=truncated,
    )


def build_import_plan(input_path: Path) -> ImportPlan:
    raw_items = load_json_array(input_path)
    duplicate_ids = _find_duplicate_ids(raw_items)
    frequency_map = build_series_frequency(
        [
            raw.get("series") if isinstance(raw, dict) else None
            for raw in raw_items
        ]
    )

    conversions: list[ItemConversion] = []
    for index, raw in enumerate(raw_items):
        conversions.append(
            convert_legacy_item(
                raw,
                source_index=index,
                frequency_map=frequency_map,
                duplicate_ids=duplicate_ids,
            )
        )

    plan = ImportPlan(
        source_path=input_path,
        source_filename=input_path.name,
        source_sha256=compute_file_sha256(input_path),
        source_total=len(raw_items),
    )

    eligible: list[ItemConversion] = []
    for conv in conversions:
        if "MISSING_CATEGORY" in conv.error_codes:
            plan.skipped_missing_category.append(
                SkippedMissingCategory(
                    source_id=conv.source_id,
                    source_index=conv.source_index,
                    title=conv.title,
                    original_data=conv.original_data,
                )
            )
            continue

        if not conv.is_convertible:
            plan.invalid_items.append(conv)
            continue

        eligible.append(conv)

    title_groups: dict[tuple[str, str], list[ItemConversion]] = defaultdict(list)
    for conv in eligible:
        assert conv.category_name and conv.title
        title_groups[(conv.category_name, conv.title)].append(conv)

    skipped_source_ids: set[int] = set()
    for group in title_groups.values():
        if len(group) < 2:
            continue
        selection = pick_duplicate_winner(group)
        plan.skipped_duplicate_titles.append(selection)
        for skipped in selection.skipped:
            if skipped.source_id is not None:
                skipped_source_ids.add(skipped.source_id)

    for conv in eligible:
        if conv.source_id in skipped_source_ids:
            continue
        planned = _to_planned(conv)
        plan.to_import.append(planned)
        if planned.cleared_ambiguous:
            plan.cleared_ambiguous_series.append(planned)

    return plan
