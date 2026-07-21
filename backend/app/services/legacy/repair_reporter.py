"""Write legacy import repair reports."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

REPAIR_REPORT_FILES = (
    "repair-summary.json",
    "title-repair.json",
    "collection-repairs.json",
    "additional-collection-candidates.csv",
    "repair-verification.json",
)


def resolve_run_report_dir(
    report_dir: Path,
    *,
    dry_run: bool,
    started_at: datetime,
) -> Path:
    """Create a timestamped run directory so reports are not overwritten."""
    mode = "dry-run" if dry_run else "apply"
    stamp = started_at.strftime("%Y%m%dT%H%M%S") + f"{started_at.microsecond:06d}"
    run_dir = report_dir / "runs" / f"{stamp}-{mode}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_json(path: Path, data: Any, *, pretty: bool) -> None:
    indent = 2 if pretty else None
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=indent, default=str)
        handle.write("\n")


def write_repair_reports(
    report_dir: Path,
    *,
    summary: dict[str, Any],
    title_repair: dict[str, Any],
    collection_repairs: list[dict[str, Any]],
    additional_candidates: list[dict[str, Any]],
    verification: dict[str, Any],
    pretty: bool,
) -> list[Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    summary_path = report_dir / "repair-summary.json"
    _write_json(summary_path, summary, pretty=pretty)
    written.append(summary_path)

    title_path = report_dir / "title-repair.json"
    _write_json(title_path, title_repair, pretty=pretty)
    written.append(title_path)

    collections_path = report_dir / "collection-repairs.json"
    _write_json(collections_path, collection_repairs, pretty=pretty)
    written.append(collections_path)

    candidates_path = report_dir / "additional-collection-candidates.csv"
    fieldnames = [
        "progress_note",
        "item_count",
        "category_names",
        "item_ids",
        "titles",
        "suggested_collection_name",
        "reason",
        "applied",
    ]
    with candidates_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in additional_candidates:
            writer.writerow(row)
    written.append(candidates_path)

    verification_path = report_dir / "repair-verification.json"
    _write_json(verification_path, verification, pretty=pretty)
    written.append(verification_path)

    return written
