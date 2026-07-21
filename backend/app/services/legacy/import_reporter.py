"""Write legacy import result reports."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.legacy.import_plan import ImportPlan, PlannedImportItem
from app.services.legacy.selection import record_summary

IMPORT_REPORT_FILES = (
    "import-summary.json",
    "imported-items.json",
    "skipped-missing-category.json",
    "skipped-duplicate-titles.json",
    "cleared-ambiguous-series.json",
    "created-collections.json",
    "verification.json",
)


def _write_json(path: Path, data: Any, *, pretty: bool) -> None:
    indent = 2 if pretty else None
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=indent, default=str)
        handle.write("\n")


def build_import_summary(
    plan: ImportPlan,
    *,
    status: str,
    started_at: datetime,
    completed_at: datetime | None,
    created_collections: int,
    planned_count: int,
    completed_count: int,
    dry_run: bool,
) -> dict[str, Any]:
    return {
        "source_total": plan.source_total,
        "eligible_after_validation": plan.eligible_after_validation,
        "imported_items": plan.imported_items_count,
        "created_collections": created_collections,
        "skipped_missing_category": plan.skipped_missing_category_count,
        "skipped_duplicate_titles": plan.skipped_duplicate_titles_count,
        "cleared_ambiguous_series": plan.cleared_ambiguous_series_count,
        "planned_count": planned_count,
        "completed_count": completed_count,
        "status": status,
        "dry_run": dry_run,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat() if completed_at else None,
        "source_sha256": plan.source_sha256,
        "source_filename": plan.source_filename,
    }


def build_verification(
    plan: ImportPlan,
    *,
    db_item_count: int | None,
    db_planned_count: int | None,
    db_completed_count: int | None,
    db_collection_linked_count: int | None,
    db_progress_note_count: int | None,
    db_ambiguous_as_collection_count: int | None,
    category_counts: dict[str, int] | None,
) -> dict[str, Any]:
    imported = plan.imported_items_count
    skipped_cat = plan.skipped_missing_category_count
    skipped_dup = plan.skipped_duplicate_titles_count
    equation_lhs = plan.source_total
    equation_rhs = imported + skipped_cat + skipped_dup

    return {
        "source_equation": f"{equation_lhs} = {imported} + {skipped_cat} + {skipped_dup}",
        "source_equation_valid": equation_lhs == equation_rhs,
        "source_total": plan.source_total,
        "imported_items": imported,
        "skipped_missing_category": skipped_cat,
        "skipped_duplicate_titles": skipped_dup,
        "db_item_count": db_item_count,
        "db_planned_count": db_planned_count,
        "db_completed_count": db_completed_count,
        "db_collection_linked_count": db_collection_linked_count,
        "db_progress_note_count": db_progress_note_count,
        "db_ambiguous_as_collection_count": db_ambiguous_as_collection_count,
        "cleared_ambiguous_series": plan.cleared_ambiguous_series_count,
        "category_item_counts": category_counts or {},
    }


def _planned_to_dict(item: PlannedImportItem) -> dict[str, Any]:
    return {
        "source_id": item.source_id,
        "source_index": item.source_index,
        "category_name": item.category_name,
        "title": item.title,
        "status": item.status,
        "rating": item.rating,
        "collection_name": item.collection_name,
        "progress_note": item.progress_note,
        "cleared_ambiguous": item.cleared_ambiguous,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def write_import_reports(
    report_dir: Path,
    plan: ImportPlan,
    *,
    summary: dict[str, Any],
    verification: dict[str, Any],
    created_collections: list[dict[str, Any]],
    imported_with_ids: list[dict[str, Any]] | None,
    pretty: bool,
) -> list[Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    summary_path = report_dir / "import-summary.json"
    _write_json(summary_path, summary, pretty=pretty)
    written.append(summary_path)

    imported_path = report_dir / "imported-items.json"
    payload = imported_with_ids if imported_with_ids is not None else [
        _planned_to_dict(item) for item in plan.to_import
    ]
    _write_json(imported_path, payload, pretty=pretty)
    written.append(imported_path)

    skipped_cat_path = report_dir / "skipped-missing-category.json"
    _write_json(
        skipped_cat_path,
        [
            {
                "source_id": row.source_id,
                "source_index": row.source_index,
                "title": row.title,
                "disposition": row.disposition,
                "original_data": row.original_data,
            }
            for row in plan.skipped_missing_category
        ],
        pretty=pretty,
    )
    written.append(skipped_cat_path)

    dup_path = report_dir / "skipped-duplicate-titles.json"
    _write_json(
        dup_path,
        [
            {
                "category_name": sel.category_name,
                "title": sel.title,
                "kept_source_id": sel.kept.source_id,
                "skipped_source_ids": [c.source_id for c in sel.skipped],
                "selection_reason": sel.selection_reason,
                "kept_record_summary": record_summary(sel.kept),
                "skipped_record_summaries": [record_summary(c) for c in sel.skipped],
            }
            for sel in plan.skipped_duplicate_titles
        ],
        pretty=pretty,
    )
    written.append(dup_path)

    ambiguous_path = report_dir / "cleared-ambiguous-series.json"
    _write_json(
        ambiguous_path,
        [_planned_to_dict(item) for item in plan.cleared_ambiguous_series],
        pretty=pretty,
    )
    written.append(ambiguous_path)

    collections_path = report_dir / "created-collections.json"
    _write_json(collections_path, created_collections, pretty=pretty)
    written.append(collections_path)

    verification_path = report_dir / "verification.json"
    _write_json(verification_path, verification, pretty=pretty)
    written.append(verification_path)

    return written
