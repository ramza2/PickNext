"""Dry-run analysis CLI for legacy movie.json (no database writes)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.services.legacy.analyzer import analyze_legacy_movies
from app.services.legacy.reporter import write_reports


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze legacy-data/movie.json and write dry-run migration reports. "
            "Does not INSERT/UPDATE/DELETE any database rows."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to movie.json",
    )
    parser.add_argument(
        "--report-dir",
        required=True,
        type=Path,
        help="Directory for migration-report outputs",
    )
    parser.add_argument(
        "--category-input",
        type=Path,
        default=None,
        help="Optional category.json for seed mapping cross-check",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON report files",
    )
    parser.add_argument(
        "--fail-on-critical",
        action="store_true",
        help="Exit with code 1 when critical errors are present",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path: Path = args.input
    if not input_path.is_file():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 2

    result = analyze_legacy_movies(
        input_path,
        category_input=args.category_input,
    )
    written = write_reports(result, args.report_dir, pretty=args.pretty)

    summary = result.summary.to_dict()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Reports written to: {args.report_dir}")
    for path in written:
        print(f"  - {path.name}")

    if args.fail_on_critical and result.summary.critical_errors > 0:
        print(
            f"Failing due to {result.summary.critical_errors} critical error(s).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
