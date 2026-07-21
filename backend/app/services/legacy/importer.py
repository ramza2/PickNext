"""Execute legacy movie.json import into PostgreSQL."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    Category,
    Collection,
    Item,
    ItemStatus,
    LegacyImportCollection,
    LegacyImportDisposition,
    LegacyImportItem,
    LegacyImportRun,
    LegacyImportRunStatus,
    User,
)
from app.services.legacy.import_plan import ImportPlan, PlannedImportItem, build_import_plan
from app.services.legacy.import_reporter import (
    build_import_summary,
    build_verification,
    write_import_reports,
)
from app.services.legacy.selection import record_summary

logger = logging.getLogger(__name__)


class ImportBlockedError(Exception):
    """Raised when import cannot proceed due to policy."""


class ImportEnvironmentError(Exception):
    """Raised when environment does not allow the requested operation."""


@dataclass
class ImportResult:
    plan: ImportPlan
    summary: dict[str, object]
    verification: dict[str, object]
    report_paths: list[Path]
    import_run_id: UUID | None = None


def find_user(db: Session, email: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise ImportBlockedError(f"Seed 사용자를 찾을 수 없습니다: {email}")
    return user


def find_successful_import_run(
    db: Session,
    *,
    user_id: UUID,
    source_sha256: str,
) -> LegacyImportRun | None:
    return db.scalar(
        select(LegacyImportRun).where(
            LegacyImportRun.user_id == user_id,
            LegacyImportRun.source_sha256 == source_sha256,
            LegacyImportRun.status == LegacyImportRunStatus.SUCCESS,
        )
    )


def reset_imported_data(
    db: Session,
    *,
    user_id: UUID,
    source_sha256: str,
) -> LegacyImportRun:
    settings = get_settings()
    if settings.app_env.lower() in {"production", "prod"}:
        raise ImportEnvironmentError(
            "--reset-imported-data는 프로덕션 환경에서 실행할 수 없습니다."
        )

    run = find_successful_import_run(db, user_id=user_id, source_sha256=source_sha256)
    if run is None:
        raise ImportBlockedError("삭제할 성공 Import 이력이 없습니다.")

    item_ids = [
        row
        for row in db.scalars(
            select(LegacyImportItem.item_id).where(
                LegacyImportItem.import_run_id == run.id,
                LegacyImportItem.disposition == LegacyImportDisposition.IMPORTED,
                LegacyImportItem.item_id.is_not(None),
            )
        )
        if row is not None
    ]

    collection_ids = list(
        db.scalars(
            select(LegacyImportCollection.collection_id).where(
                LegacyImportCollection.import_run_id == run.id
            )
        )
    )

    if item_ids:
        db.execute(delete(Item).where(Item.id.in_(item_ids)))

    if collection_ids:
        db.execute(delete(Collection).where(Collection.id.in_(collection_ids)))

    db.delete(run)
    db.flush()
    logger.info(
        "Reset import run %s: deleted %d items, %d collections",
        run.id,
        len(item_ids),
        len(collection_ids),
    )
    return run


def _load_category_map(db: Session, user_id: UUID) -> dict[str, Category]:
    categories = db.scalars(select(Category).where(Category.user_id == user_id)).all()
    return {category.name: category for category in categories}


def _count_statuses(plan: ImportPlan) -> tuple[int, int]:
    planned = sum(1 for item in plan.to_import if item.status == "PLANNED")
    completed = sum(1 for item in plan.to_import if item.status == "COMPLETED")
    return planned, completed


def _collect_collection_names(plan: ImportPlan) -> list[str]:
    names: set[str] = set()
    for item in plan.to_import:
        if item.collection_name:
            names.add(item.collection_name)
    return sorted(names)


def _verify_db_counts(
    db: Session,
    *,
    user_id: UUID,
    import_run_id: UUID,
    plan: ImportPlan,
    ambiguous_source_ids: set[int],
    imported_row_count: int,
) -> dict[str, object]:
    db.flush()
    db_item_count = db.scalar(
        select(func.count())
        .select_from(LegacyImportItem)
        .where(
            LegacyImportItem.import_run_id == import_run_id,
            LegacyImportItem.disposition == LegacyImportDisposition.IMPORTED,
        )
    )

    item_ids = list(
        db.scalars(
            select(LegacyImportItem.item_id).where(
                LegacyImportItem.import_run_id == import_run_id,
                LegacyImportItem.disposition == LegacyImportDisposition.IMPORTED,
                LegacyImportItem.item_id.is_not(None),
            )
        )
    )

    db_planned = db.scalar(
        select(func.count())
        .select_from(Item)
        .where(Item.id.in_(item_ids), Item.status == ItemStatus.PLANNED)
    ) if item_ids else 0

    db_completed = db.scalar(
        select(func.count())
        .select_from(Item)
        .where(Item.id.in_(item_ids), Item.status == ItemStatus.COMPLETED)
    ) if item_ids else 0

    db_collection_linked = db.scalar(
        select(func.count())
        .select_from(Item)
        .where(Item.id.in_(item_ids), Item.collection_id.is_not(None))
    ) if item_ids else 0

    db_progress_note = db.scalar(
        select(func.count())
        .select_from(Item)
        .where(Item.id.in_(item_ids), Item.progress_note.is_not(None))
    ) if item_ids else 0

    db_ambiguous_as_collection = 0
    if ambiguous_source_ids and item_ids:
        db_ambiguous_as_collection = db.scalar(
            select(func.count())
            .select_from(Item)
            .join(LegacyImportItem, LegacyImportItem.item_id == Item.id)
            .where(
                LegacyImportItem.import_run_id == import_run_id,
                LegacyImportItem.source_id.in_(ambiguous_source_ids),
                Item.collection_id.is_not(None),
            )
        ) or 0

    category_counts: dict[str, int] = {}
    if item_ids:
        rows = db.execute(
            select(Category.name, func.count())
            .select_from(Item)
            .join(Category, Category.id == Item.category_id)
            .where(Item.id.in_(item_ids))
            .group_by(Category.name)
        ).all()
        category_counts = {name: count for name, count in rows}

    return build_verification(
        plan,
        db_item_count=db_item_count,
        db_planned_count=db_planned,
        db_completed_count=db_completed,
        db_collection_linked_count=db_collection_linked,
        db_progress_note_count=db_progress_note,
        db_ambiguous_as_collection_count=db_ambiguous_as_collection,
        category_counts=category_counts,
    )


def run_legacy_import(
    db: Session,
    *,
    input_path: Path,
    report_dir: Path,
    user_email: str | None = None,
    dry_run: bool = False,
    apply: bool = False,
    reset_imported_data_flag: bool = False,
    pretty: bool = False,
    commit: bool = True,
) -> ImportResult:
    if dry_run == apply:
        raise ImportBlockedError("--dry-run 또는 --apply 중 하나만 지정해야 합니다.")

    settings = get_settings()
    email = user_email or settings.seed_user_email
    started_at = datetime.now(timezone.utc)

    plan = build_import_plan(input_path)
    user = find_user(db, email)

    if reset_imported_data_flag:
        if dry_run:
            raise ImportBlockedError("--reset-imported-data는 --apply와 함께만 사용할 수 있습니다.")
        reset_imported_data(db, user_id=user.id, source_sha256=plan.source_sha256)

    existing = find_successful_import_run(
        db, user_id=user.id, source_sha256=plan.source_sha256
    )
    if existing is not None and apply:
        raise ImportBlockedError(
            "동일 파일(SHA-256)의 성공 Import 이력이 있습니다. "
            "재실행하려면 --reset-imported-data를 함께 지정하세요."
        )

    planned_count, completed_count = _count_statuses(plan)
    collection_names = _collect_collection_names(plan)
    created_collections_preview = [{"name": name} for name in collection_names]

    if dry_run:
        summary = build_import_summary(
            plan,
            status="DRY_RUN",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            created_collections=len(collection_names),
            planned_count=planned_count,
            completed_count=completed_count,
            dry_run=True,
        )
        verification = build_verification(
            plan,
            db_item_count=None,
            db_planned_count=planned_count,
            db_completed_count=completed_count,
            db_collection_linked_count=sum(1 for i in plan.to_import if i.collection_name),
            db_progress_note_count=sum(1 for i in plan.to_import if i.progress_note),
            db_ambiguous_as_collection_count=0,
            category_counts=_category_counts_from_plan(plan),
        )
        report_paths = write_import_reports(
            report_dir,
            plan,
            summary=summary,
            verification=verification,
            created_collections=created_collections_preview,
            imported_with_ids=None,
            pretty=pretty,
        )
        return ImportResult(
            plan=plan,
            summary=summary,
            verification=verification,
            report_paths=report_paths,
        )

    import_run = LegacyImportRun(
        user_id=user.id,
        source_filename=plan.source_filename,
        source_sha256=plan.source_sha256,
        source_total_count=plan.source_total,
        imported_item_count=0,
        skipped_count=plan.skipped_missing_category_count + plan.skipped_duplicate_titles_count,
        status=LegacyImportRunStatus.IN_PROGRESS,
    )
    db.add(import_run)
    db.flush()

    category_map = _load_category_map(db, user.id)
    missing_seed = {
        item.category_name
        for item in plan.to_import
        if item.category_name not in category_map
    }
    if missing_seed:
        raise ImportBlockedError(f"Seed 카테고리가 없습니다: {sorted(missing_seed)}")

    collection_by_name: dict[str, Collection] = {}
    created_collections: list[dict[str, object]] = []

    try:
        for name in collection_names:
            existing_collection = db.scalar(
                select(Collection).where(
                    Collection.user_id == user.id,
                    Collection.name == name,
                )
            )
            if existing_collection is not None:
                collection_by_name[name] = existing_collection
                continue

            collection = Collection(user_id=user.id, name=name)
            db.add(collection)
            db.flush()
            collection_by_name[name] = collection
            db.add(
                LegacyImportCollection(
                    import_run_id=import_run.id,
                    collection_id=collection.id,
                    collection_name=name,
                )
            )
            created_collections.append(
                {"collection_id": str(collection.id), "name": name, "created": True}
            )

        imported_rows: list[dict[str, object]] = []
        ambiguous_source_ids = {
            item.source_id for item in plan.cleared_ambiguous_series
        }

        for planned in plan.to_import:
            category = category_map[planned.category_name]
            collection_id = (
                collection_by_name[planned.collection_name].id
                if planned.collection_name
                else None
            )
            item = Item(
                user_id=user.id,
                category_id=category.id,
                collection_id=collection_id,
                title=planned.title,
                status=ItemStatus(planned.status),
                rating=Decimal(str(planned.rating)),
                progress_note=planned.progress_note,
                memo=None,
                created_at=planned.created_at,
                updated_at=planned.updated_at,
            )
            db.add(item)
            db.flush()
            db.add(
                LegacyImportItem(
                    import_run_id=import_run.id,
                    item_id=item.id,
                    source_id=planned.source_id,
                    disposition=LegacyImportDisposition.IMPORTED,
                )
            )
            imported_rows.append(
                {
                    "source_id": planned.source_id,
                    "item_id": str(item.id),
                    "category_name": planned.category_name,
                    "title": planned.title,
                    "status": planned.status,
                    "rating": planned.rating,
                    "collection_name": planned.collection_name,
                    "progress_note": planned.progress_note,
                    "cleared_ambiguous": planned.cleared_ambiguous,
                }
            )

        for skipped in plan.skipped_missing_category:
            if skipped.source_id is not None:
                db.add(
                    LegacyImportItem(
                        import_run_id=import_run.id,
                        item_id=None,
                        source_id=skipped.source_id,
                        disposition=LegacyImportDisposition.SKIPPED_MISSING_CATEGORY,
                    )
                )

        for selection in plan.skipped_duplicate_titles:
            for skipped in selection.skipped:
                if skipped.source_id is not None:
                    db.add(
                        LegacyImportItem(
                            import_run_id=import_run.id,
                            item_id=None,
                            source_id=skipped.source_id,
                            disposition=LegacyImportDisposition.SKIPPED_DUPLICATE_TITLE,
                        )
                    )

        verification = _verify_db_counts(
            db,
            user_id=user.id,
            import_run_id=import_run.id,
            plan=plan,
            ambiguous_source_ids=ambiguous_source_ids,
            imported_row_count=len(imported_rows),
        )

        if not verification["source_equation_valid"]:
            raise RuntimeError(f"검증식 불일치: {verification['source_equation']}")

        if len(imported_rows) != plan.imported_items_count:
            raise RuntimeError(
                f"Import row 수 불일치: expected {plan.imported_items_count}, "
                f"got {len(imported_rows)}"
            )

        if verification["db_item_count"] != plan.imported_items_count:
            raise RuntimeError(
                f"DB LegacyImportItem 수 불일치: expected {plan.imported_items_count}, "
                f"got {verification['db_item_count']}"
            )

        if verification["db_ambiguous_as_collection_count"]:
            raise RuntimeError("Ambiguous series가 Collection으로 연결되었습니다.")

        import_run.imported_item_count = plan.imported_items_count
        import_run.skipped_count = (
            plan.skipped_missing_category_count + plan.skipped_duplicate_titles_count
        )
        import_run.status = LegacyImportRunStatus.SUCCESS
        import_run.completed_at = datetime.now(timezone.utc)

        summary = build_import_summary(
            plan,
            status="SUCCESS",
            started_at=started_at,
            completed_at=import_run.completed_at,
            created_collections=len(created_collections),
            planned_count=planned_count,
            completed_count=completed_count,
            dry_run=False,
        )

        report_paths = write_import_reports(
            report_dir,
            plan,
            summary=summary,
            verification=verification,
            created_collections=created_collections or created_collections_preview,
            imported_with_ids=imported_rows,
            pretty=pretty,
        )

        db.commit() if commit else db.flush()
        return ImportResult(
            plan=plan,
            summary=summary,
            verification=verification,
            report_paths=report_paths,
            import_run_id=import_run.id,
        )
    except Exception:
        db.rollback()
        raise


def _category_counts_from_plan(plan: ImportPlan) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in plan.to_import:
        counts[item.category_name] = counts.get(item.category_name, 0) + 1
    return counts
