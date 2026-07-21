"""CLI for legacy movie.json import into PostgreSQL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.db.session import SessionLocal
from app.services.legacy.importer import (
    ImportBlockedError,
    ImportEnvironmentError,
    run_legacy_import,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import legacy movie.json into PostgreSQL with confirmed policies."
    )
    parser.add_argument("--input", required=True, type=Path, help="Path to movie.json")
    parser.add_argument(
        "--report-dir",
        required=True,
        type=Path,
        help="Directory for import reports",
    )
    parser.add_argument(
        "--category-input",
        type=Path,
        default=None,
        help="Optional category.json (currently unused; reserved for validation)",
    )
    parser.add_argument(
        "--user-email",
        type=str,
        default=None,
        help="Target user email (default: SEED_USER_EMAIL)",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Plan import without DB writes")
    mode.add_argument("--apply", action="store_true", help="Execute import in one transaction")
    parser.add_argument(
        "--reset-imported-data",
        action="store_true",
        help="Development only: remove prior successful import for the same file",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.input.is_file():
        print(f"Input file not found: {args.input}", file=sys.stderr)
        return 2

    session = SessionLocal()
    try:
        result = run_legacy_import(
            session,
            input_path=args.input,
            report_dir=args.report_dir,
            user_email=args.user_email,
            dry_run=args.dry_run,
            apply=args.apply,
            reset_imported_data_flag=args.reset_imported_data,
            pretty=args.pretty,
        )
    except (ImportBlockedError, ImportEnvironmentError, ValueError) as exc:
        session.rollback()
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        session.rollback()
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()

    print(json.dumps(result.summary, ensure_ascii=False, indent=2, default=str))
    print(f"Reports written to: {args.report_dir}")
    for path in result.report_paths:
        print(f"  - {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
