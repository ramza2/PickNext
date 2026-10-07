"""Restore Legacy Progress Notes truncated at 200 characters during import.

Safety:
- Only PROGRESS_NOTE classifications from movie.json with full length > 200
- Map via LegacyImportItem.source_id → item_id (never title-only)
- Update only when current DB value equals the historical truncated value
- Never overwrite user-edited notes or ambiguous mappings
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Item,
    LegacyImportDisposition,
    LegacyImportItem,
    LegacyImportRun,
    LegacyImportRunStatus,
)
from app.services.legacy.analyzer import load_json_array
from app.services.legacy.repair import RepairBlockedError, find_user
from app.services.legacy.series_classifier import (
    SeriesClassification,
    build_series_frequency,
)
from app.services.legacy.transformer import convert_legacy_item


class RestoreStatus(str, Enum):
    WOULD_UPDATE = "WOULD_UPDATE"
    UPDATED = "UPDATED"
    ALREADY_FULL = "ALREADY_FULL"
    CONFLICT = "CONFLICT"
    MISSING_MAPPING = "MISSING_MAPPING"
    AMBIGUOUS_MAPPING = "AMBIGUOUS_MAPPING"
    ITEM_MISSING = "ITEM_MISSING"
    WRONG_USER = "WRONG_USER"


@dataclass
class RestoreCandidate:
    source_id: int
    title: str | None
    item_id: UUID | None
    legacy_length: int
    current_length: int | None
    status: RestoreStatus
    full_note: str
    expected_old_value: str
    current_note: str | None = None


@dataclass
class RestoreResult:
    dry_run: bool
    user_email: str
    source_candidates: int = 0
    mapped: int = 0
    would_update: int = 0
    updated: int = 0
    already_full: int = 0
    conflicts: int = 0
    missing_mapping: int = 0
    ambiguous_mapping: int = 0
    item_missing: int = 0
    wrong_user: int = 0
    candidates: list[RestoreCandidate] = field(default_factory=list)
    blocked: bool = False
    block_reason: str | None = None

    def to_summary(self) -> dict[str, object]:
        return {
            "mode": "DRY_RUN" if self.dry_run else "APPLY",
            "user_email": self.user_email,
            "source_candidates": self.source_candidates,
            "mapped": self.mapped,
            "would_update": self.would_update,
            "updated": self.updated,
            "already_full": self.already_full,
            "conflicts": self.conflicts,
            "missing_mapping": self.missing_mapping,
            "ambiguous_mapping": self.ambiguous_mapping,
            "item_missing": self.item_missing,
            "wrong_user": self.wrong_user,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "candidates": [
                {
                    "source_id": row.source_id,
                    "title": row.title,
                    "item_id": str(row.item_id) if row.item_id else None,
                    "legacy_length": row.legacy_length,
                    "current_length": row.current_length,
                    "status": row.status.value,
                }
                for row in self.candidates
            ],
        }


def _find_duplicate_ids(raw_items: list[object]) -> set[int]:
    seen: set[int] = set()
    duplicates: set[int] = set()
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        raw_id = raw.get("id")
        if isinstance(raw_id, int) and not isinstance(raw_id, bool):
            if raw_id in seen:
                duplicates.add(raw_id)
            else:
                seen.add(raw_id)
    return duplicates


def _find_truncated_progress_notes(
    movie_path: Path,
) -> list[tuple[int, str | None, str]]:
    """Return (source_id, title, full_note) for PROGRESS_NOTE series longer than 200."""
    raw_items = load_json_array(movie_path)
    duplicate_ids = _find_duplicate_ids(raw_items)
    frequency_map = build_series_frequency(
        [raw.get("series") if isinstance(raw, dict) else None for raw in raw_items]
    )

    found: list[tuple[int, str | None, str]] = []
    for index, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            continue
        conv = convert_legacy_item(
            raw,
            source_index=index,
            frequency_map=frequency_map,
            duplicate_ids=duplicate_ids,
        )
        classification = conv.classification
        if classification is None:
            continue
        if classification.result != SeriesClassification.PROGRESS_NOTE:
            continue
        note = classification.suggested_progress_note
        if not isinstance(note, str):
            continue
        full_note = note.strip()
        if len(full_note) <= 200:
            continue
        if conv.source_id is None:
            continue
        title = conv.title
        if title is None and isinstance(raw.get("name"), str):
            title = raw["name"].strip() or None
        found.append((conv.source_id, title, full_note))
    return found


def _source_id_to_item_ids(db: Session, user_id: UUID) -> dict[int, set[UUID]]:
    """Map source_id → item_id set from all SUCCESS imports for the user."""
    rows = db.execute(
        select(LegacyImportItem.source_id, LegacyImportItem.item_id)
        .join(LegacyImportRun, LegacyImportItem.import_run_id == LegacyImportRun.id)
        .where(
            LegacyImportRun.user_id == user_id,
            LegacyImportRun.status == LegacyImportRunStatus.SUCCESS,
            LegacyImportItem.disposition == LegacyImportDisposition.IMPORTED,
            LegacyImportItem.item_id.is_not(None),
        )
    ).all()
    mapping: dict[int, set[UUID]] = {}
    for source_id, item_id in rows:
        if item_id is None:
            continue
        mapping.setdefault(int(source_id), set()).add(item_id)
    return mapping


def restore_legacy_progress_notes(
    db: Session,
    *,
    movie_path: Path,
    user_email: str,
    dry_run: bool,
    apply: bool,
    commit: bool = True,
) -> RestoreResult:
    if dry_run == apply:
        raise RepairBlockedError("--dry-run 또는 --apply 중 하나만 지정해야 합니다.")
    if not movie_path.is_file():
        raise RepairBlockedError(f"Input file not found: {movie_path}")

    user = find_user(db, user_email)
    result = RestoreResult(dry_run=dry_run, user_email=user.email)

    truncated_sources = _find_truncated_progress_notes(movie_path)
    result.source_candidates = len(truncated_sources)
    source_map = _source_id_to_item_ids(db, user.id)

    unsafe = False
    updates: list[tuple[Item, str, RestoreCandidate]] = []

    for source_id, title, full_note in truncated_sources:
        expected_old = full_note[:200]
        item_ids = source_map.get(source_id, set())

        if not item_ids:
            result.missing_mapping += 1
            unsafe = True
            result.candidates.append(
                RestoreCandidate(
                    source_id=source_id,
                    title=title,
                    item_id=None,
                    legacy_length=len(full_note),
                    current_length=None,
                    status=RestoreStatus.MISSING_MAPPING,
                    full_note=full_note,
                    expected_old_value=expected_old,
                )
            )
            continue

        if len(item_ids) > 1:
            result.ambiguous_mapping += 1
            unsafe = True
            result.candidates.append(
                RestoreCandidate(
                    source_id=source_id,
                    title=title,
                    item_id=None,
                    legacy_length=len(full_note),
                    current_length=None,
                    status=RestoreStatus.AMBIGUOUS_MAPPING,
                    full_note=full_note,
                    expected_old_value=expected_old,
                )
            )
            continue

        item_id = next(iter(item_ids))
        item = db.get(Item, item_id)
        if item is None:
            result.item_missing += 1
            unsafe = True
            result.candidates.append(
                RestoreCandidate(
                    source_id=source_id,
                    title=title,
                    item_id=item_id,
                    legacy_length=len(full_note),
                    current_length=None,
                    status=RestoreStatus.ITEM_MISSING,
                    full_note=full_note,
                    expected_old_value=expected_old,
                )
            )
            continue

        if item.user_id != user.id:
            result.wrong_user += 1
            unsafe = True
            result.candidates.append(
                RestoreCandidate(
                    source_id=source_id,
                    title=title,
                    item_id=item_id,
                    legacy_length=len(full_note),
                    current_length=len(item.progress_note) if item.progress_note else 0,
                    status=RestoreStatus.WRONG_USER,
                    full_note=full_note,
                    expected_old_value=expected_old,
                    current_note=item.progress_note,
                )
            )
            continue

        result.mapped += 1
        current = item.progress_note
        current_len = len(current) if current is not None else 0

        if current == full_note:
            result.already_full += 1
            result.candidates.append(
                RestoreCandidate(
                    source_id=source_id,
                    title=title,
                    item_id=item_id,
                    legacy_length=len(full_note),
                    current_length=current_len,
                    status=RestoreStatus.ALREADY_FULL,
                    full_note=full_note,
                    expected_old_value=expected_old,
                    current_note=current,
                )
            )
            continue

        if current == expected_old:
            candidate = RestoreCandidate(
                source_id=source_id,
                title=title,
                item_id=item_id,
                legacy_length=len(full_note),
                current_length=current_len,
                status=RestoreStatus.WOULD_UPDATE,
                full_note=full_note,
                expected_old_value=expected_old,
                current_note=current,
            )
            result.would_update += 1
            result.candidates.append(candidate)
            updates.append((item, full_note, candidate))
            continue

        result.conflicts += 1
        unsafe = True
        result.candidates.append(
            RestoreCandidate(
                source_id=source_id,
                title=title,
                item_id=item_id,
                legacy_length=len(full_note),
                current_length=current_len,
                status=RestoreStatus.CONFLICT,
                full_note=full_note,
                expected_old_value=expected_old,
                current_note=current,
            )
        )

    if apply and unsafe:
        # No Item writes were made yet — leave caller session intact.
        result.blocked = True
        result.block_reason = (
            "conflict/ambiguous/missing mapping detected — no changes committed"
        )
        result.updated = 0
        return result

    if apply and updates:
        for item, full_note, candidate in updates:
            item.progress_note = full_note
            candidate.status = RestoreStatus.UPDATED
        if commit:
            db.commit()
        else:
            db.flush()
        result.updated = len(updates)
    # dry_run: never mutate DB; do not rollback caller session state.

    return result
