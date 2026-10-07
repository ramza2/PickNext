"""CLI: restore Legacy Progress Notes truncated at 200 characters."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.db.session import SessionLocal
from app.services.legacy.repair import RepairBlockedError
from app.services.legacy.restore_progress_notes import restore_legacy_progress_notes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Restore Legacy Progress Notes that were truncated to 200 characters "
            "during historical import. Uses LegacyImportItem.source_id mapping."
        )
    )
    parser.add_argument("--input", required=True, type=Path, help="Path to movie.json")
    parser.add_argument(
        "--user-email",
        required=True,
        type=str,
        help="Target user email that owns the Legacy import",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan restores without DB writes",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Apply restores in one transaction (blocked if any conflict)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON summary",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.input.is_file():
        print(f"Input file not found: {args.input}", file=sys.stderr)
        return 2

    session = SessionLocal()
    try:
        result = restore_legacy_progress_notes(
            session,
            movie_path=args.input,
            user_email=args.user_email,
            dry_run=args.dry_run,
            apply=args.apply,
        )
    except RepairBlockedError as exc:
        session.rollback()
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        session.rollback()
        print(f"Restore failed: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()

    summary = result.to_summary()
    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            default=str,
        )
    )
    if result.blocked:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
