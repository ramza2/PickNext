"""CLI for in-place legacy import data repairs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID

from app.db.session import SessionLocal
from app.services.legacy.repair import RepairBlockedError, run_legacy_import_repair


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Repair legacy import data in-place (title + collection corrections)."
    )
    parser.add_argument("--input", required=True, type=Path, help="Path to movie.json")
    parser.add_argument("--report-dir", required=True, type=Path, help="Repair report directory")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Plan repairs without DB writes")
    mode.add_argument("--apply", action="store_true", help="Apply repairs in one transaction")
    parser.add_argument("--user-email", type=str, default=None, help="Target user email")
    parser.add_argument("--import-run-id", type=str, default=None, help="Explicit import run UUID")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.input.is_file():
        print(f"Input file not found: {args.input}", file=sys.stderr)
        return 2

    import_run_id = UUID(args.import_run_id) if args.import_run_id else None
    session = SessionLocal()
    try:
        result = run_legacy_import_repair(
            session,
            movie_path=args.input,
            report_dir=args.report_dir,
            user_email=args.user_email,
            import_run_id=import_run_id,
            dry_run=args.dry_run,
            apply=args.apply,
            pretty=args.pretty,
        )
    except RepairBlockedError as exc:
        session.rollback()
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        session.rollback()
        print(f"Repair failed: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()

    print(json.dumps(result.summary, ensure_ascii=False, indent=2, default=str))
    report_run_dir = result.summary.get("report_run_dir", args.report_dir)
    print(f"Reports written to: {report_run_dir}")
    for path in result.report_paths:
        print(f"  - {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
