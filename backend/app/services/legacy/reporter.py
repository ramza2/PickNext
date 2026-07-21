"""Write dry-run migration report files (no DB access)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from app.services.legacy.types import AnalysisResult, SeriesCandidateRow


REPORT_FILES = (
    "summary.json",
    "invalid-items.json",
    "missing-category.json",
    "duplicate-source-ids.json",
    "duplicate-titles.csv",
    "collection-candidates.csv",
    "progress-note-candidates.csv",
    "ambiguous-series.csv",
    "normalized-preview.json",
)


def _write_json(path: Path, data: Any, *, pretty: bool) -> None:
    indent = 2 if pretty else None
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=indent)
        handle.write("\n")


def _write_series_csv(
    path: Path,
    rows: list[SeriesCandidateRow],
    *,
    suggested_column: str,
    include_confidence: bool,
) -> None:
    fieldnames = [
        "source_id",
        "category_id",
        "category_name",
        "title",
        "original_series",
        suggested_column,
    ]
    if include_confidence:
        fieldnames.append("confidence")
    fieldnames.append("reason")

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            payload: dict[str, Any] = {
                "source_id": row.source_id,
                "category_id": row.category_id,
                "category_name": row.category_name,
                "title": row.title,
                "original_series": row.original_series,
                suggested_column: row.suggested_name,
                "reason": row.reason,
            }
            if include_confidence:
                payload["confidence"] = (
                    row.confidence.value if row.confidence is not None else ""
                )
            writer.writerow(payload)


def write_reports(
    result: AnalysisResult,
    report_dir: Path,
    *,
    pretty: bool = False,
) -> list[Path]:
    """Create all migration-report files. Returns written paths."""
    report_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    summary_path = report_dir / "summary.json"
    _write_json(summary_path, result.summary.to_dict(), pretty=pretty)
    written.append(summary_path)

    invalid_path = report_dir / "invalid-items.json"
    _write_json(
        invalid_path,
        [item.to_dict() for item in result.invalid_items],
        pretty=pretty,
    )
    written.append(invalid_path)

    missing_path = report_dir / "missing-category.json"
    _write_json(
        missing_path,
        [item.to_dict() for item in result.missing_category],
        pretty=pretty,
    )
    written.append(missing_path)

    dup_ids_path = report_dir / "duplicate-source-ids.json"
    _write_json(dup_ids_path, result.duplicate_source_ids, pretty=pretty)
    written.append(dup_ids_path)

    dup_titles_path = report_dir / "duplicate-titles.csv"
    with dup_titles_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_id",
                "source_index",
                "category_id",
                "category_name",
                "title",
                "duplicate_group_size",
            ],
        )
        writer.writeheader()
        for row in result.duplicate_titles:
            writer.writerow(
                {
                    "source_id": row.source_id,
                    "source_index": row.source_index,
                    "category_id": row.category_id,
                    "category_name": row.category_name,
                    "title": row.title,
                    "duplicate_group_size": row.duplicate_group_size,
                }
            )
    written.append(dup_titles_path)

    collection_path = report_dir / "collection-candidates.csv"
    _write_series_csv(
        collection_path,
        result.collection_candidates,
        suggested_column="suggested_collection_name",
        include_confidence=True,
    )
    written.append(collection_path)

    progress_path = report_dir / "progress-note-candidates.csv"
    _write_series_csv(
        progress_path,
        result.progress_note_candidates,
        suggested_column="suggested_progress_note",
        include_confidence=True,
    )
    written.append(progress_path)

    ambiguous_path = report_dir / "ambiguous-series.csv"
    with ambiguous_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_id",
                "category_id",
                "category_name",
                "title",
                "original_series",
                "reason",
            ],
        )
        writer.writeheader()
        for row in result.ambiguous_series:
            writer.writerow(
                {
                    "source_id": row.source_id,
                    "category_id": row.category_id,
                    "category_name": row.category_name,
                    "title": row.title,
                    "original_series": row.original_series,
                    "reason": row.reason,
                }
            )
    written.append(ambiguous_path)

    preview_path = report_dir / "normalized-preview.json"
    _write_json(
        preview_path,
        [item.to_dict() for item in result.normalized_preview],
        pretty=pretty,
    )
    written.append(preview_path)

    return written
