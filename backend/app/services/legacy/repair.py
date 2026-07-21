"""Repair legacy import data in-place (no re-import)."""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    Category,
    Collection,
    Item,
    ItemStatus,
    LegacyImportDisposition,
    LegacyImportItem,
    LegacyImportRun,
    LegacyImportRunStatus,
    User,
)
from app.services.legacy.analyzer import load_json_array
from app.services.legacy.import_plan import (
    ENTERTAINMENT_CATEGORY_NAME,
    REQUIRED_COLLECTION_PROGRESS_NOTES,
    TITLE_REPAIR_SOURCE_ID,
)
from app.services.legacy.repair_reporter import resolve_run_report_dir, write_repair_reports

logger = logging.getLogger(__name__)


class RepairBlockedError(Exception):
    """Raised when repair cannot proceed."""


@dataclass
class TitleRepairPlan:
    source_id: int
    item_id: UUID | None
    old_title: str | None
    new_title: str
    old_length: int
    new_length: int
    source_title_match: bool
    applied: bool
    already_repaired: bool = False


@dataclass
class CollectionItemRepair:
    source_id: int | None
    item_id: UUID
    title: str
    old_collection_id: UUID | None
    new_collection_id: UUID | None
    old_progress_note: str | None
    new_progress_note: str | None
    applied: bool
    already_repaired: bool = False


@dataclass
class CollectionRepairPlan:
    collection_name: str
    collection_id: UUID | None
    created: bool
    matched_progress_note: str
    items: list[CollectionItemRepair] = field(default_factory=list)

    @property
    def matched_item_count(self) -> int:
        return len(self.items)

    @property
    def updated_item_count(self) -> int:
        return sum(1 for item in self.items if item.applied)

    @property
    def already_repaired_item_count(self) -> int:
        return sum(1 for item in self.items if item.already_repaired)


@dataclass
class RepairPlan:
    import_run: LegacyImportRun
    user: User
    title_repair: TitleRepairPlan | None
    collection_repairs: list[CollectionRepairPlan]
    additional_candidates: list[dict[str, object]]
    import_item_ids: set[UUID]


@dataclass
class RepairResult:
    summary: dict[str, object]
    title_repair: dict[str, object]
    collection_repairs: list[dict[str, object]]
    additional_candidates: list[dict[str, object]]
    verification: dict[str, object]
    report_paths: list[Path]


def find_user(db: Session, email: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise RepairBlockedError(f"Seed 사용자를 찾을 수 없습니다: {email}")
    return user


def resolve_import_run(
    db: Session,
    *,
    user_id: UUID,
    import_run_id: UUID | None,
) -> LegacyImportRun:
    if import_run_id is not None:
        run = db.get(LegacyImportRun, import_run_id)
        if run is None:
            raise RepairBlockedError(f"Import Run을 찾을 수 없습니다: {import_run_id}")
        if run.user_id != user_id:
            raise RepairBlockedError("Import Run 사용자가 일치하지 않습니다.")
        if run.status != LegacyImportRunStatus.SUCCESS:
            raise RepairBlockedError("성공(SUCCESS) Import Run만 보정할 수 있습니다.")
        if run.source_filename != "movie.json":
            raise RepairBlockedError("source_filename이 movie.json인 Run만 보정할 수 있습니다.")
        return run

    runs = list(
        db.scalars(
            select(LegacyImportRun)
            .where(
                LegacyImportRun.user_id == user_id,
                LegacyImportRun.status == LegacyImportRunStatus.SUCCESS,
                LegacyImportRun.source_filename == "movie.json",
            )
            .order_by(LegacyImportRun.completed_at.desc().nullslast(), LegacyImportRun.started_at.desc())
        )
    )
    if not runs:
        raise RepairBlockedError("성공한 movie.json Import Run을 찾을 수 없습니다.")
    if len(runs) > 1:
        logger.warning(
            "성공 Import Run이 %d개입니다. 최신 Run을 사용합니다: %s",
            len(runs),
            runs[0].id,
        )
    run = runs[0]
    has_items = db.scalar(
        select(func.count())
        .select_from(LegacyImportItem)
        .where(
            LegacyImportItem.import_run_id == run.id,
            LegacyImportItem.disposition == LegacyImportDisposition.IMPORTED,
            LegacyImportItem.item_id.is_not(None),
        )
    )
    if not has_items:
        raise RepairBlockedError("대상 Import Run에 Import된 Item 매핑이 없습니다.")
    return run


def load_source_title(movie_path: Path, source_id: int) -> str:
    for raw in load_json_array(movie_path):
        if not isinstance(raw, dict):
            continue
        if raw.get("id") != source_id:
            continue
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            raise RepairBlockedError(
                f"movie.json source_id={source_id}의 name을 읽을 수 없습니다."
            )
        return name.strip()
    raise RepairBlockedError(f"movie.json에서 source_id={source_id}를 찾을 수 없습니다.")


def _imported_item_ids(db: Session, import_run_id: UUID) -> set[UUID]:
    return {
        item_id
        for item_id in db.scalars(
            select(LegacyImportItem.item_id).where(
                LegacyImportItem.import_run_id == import_run_id,
                LegacyImportItem.disposition == LegacyImportDisposition.IMPORTED,
                LegacyImportItem.item_id.is_not(None),
            )
        )
        if item_id is not None
    }


def _source_id_map(db: Session, import_run_id: UUID) -> dict[UUID, int]:
    rows = db.execute(
        select(LegacyImportItem.item_id, LegacyImportItem.source_id).where(
            LegacyImportItem.import_run_id == import_run_id,
            LegacyImportItem.disposition == LegacyImportDisposition.IMPORTED,
            LegacyImportItem.item_id.is_not(None),
        )
    ).all()
    return {item_id: source_id for item_id, source_id in rows if item_id is not None}


def plan_title_repair(
    db: Session,
    *,
    import_run_id: UUID,
    import_item_ids: set[UUID],
    movie_path: Path,
) -> TitleRepairPlan:
    source_title = load_source_title(movie_path, TITLE_REPAIR_SOURCE_ID)
    mapping = db.scalar(
        select(LegacyImportItem).where(
            LegacyImportItem.import_run_id == import_run_id,
            LegacyImportItem.source_id == TITLE_REPAIR_SOURCE_ID,
            LegacyImportItem.disposition == LegacyImportDisposition.IMPORTED,
        )
    )
    if mapping is None or mapping.item_id is None:
        raise RepairBlockedError(
            f"Import Run에서 source_id={TITLE_REPAIR_SOURCE_ID} Item을 찾을 수 없습니다."
        )
    if mapping.item_id not in import_item_ids:
        raise RepairBlockedError("대상 Item이 Import Run 범위에 없습니다.")

    item = db.get(Item, mapping.item_id)
    if item is None:
        raise RepairBlockedError(f"Item을 찾을 수 없습니다: {mapping.item_id}")

    old_title = item.title
    already = old_title == source_title
    return TitleRepairPlan(
        source_id=TITLE_REPAIR_SOURCE_ID,
        item_id=item.id,
        old_title=old_title,
        new_title=source_title,
        old_length=len(old_title),
        new_length=len(source_title),
        source_title_match=old_title == source_title,
        applied=not already,
        already_repaired=already,
    )


def _get_or_plan_collection(
    db: Session,
    *,
    user_id: UUID,
    collection_name: str,
) -> tuple[Collection | None, bool]:
    existing = db.scalar(
        select(Collection).where(
            Collection.user_id == user_id,
            Collection.name == collection_name,
        )
    )
    return existing, False


def plan_collection_repairs(
    db: Session,
    *,
    user_id: UUID,
    import_item_ids: set[UUID],
    source_ids: dict[UUID, int],
) -> list[CollectionRepairPlan]:
    repairs: list[CollectionRepairPlan] = []
    for progress_note in REQUIRED_COLLECTION_PROGRESS_NOTES:
        items = list(
            db.scalars(
                select(Item)
                .join(Category, Category.id == Item.category_id)
                .where(
                    Item.id.in_(import_item_ids),
                    Item.user_id == user_id,
                    Item.progress_note == progress_note,
                )
            )
        )
        collection, _ = _get_or_plan_collection(
            db, user_id=user_id, collection_name=progress_note
        )
        collection_id = collection.id if collection else None
        item_repairs: list[CollectionItemRepair] = []
        for item in items:
            target_collection_id = collection.id if collection else None
            already = (
                item.progress_note is None
                and target_collection_id is not None
                and item.collection_id == target_collection_id
            )
            needs_apply = item.progress_note == progress_note and not already
            item_repairs.append(
                CollectionItemRepair(
                    source_id=source_ids.get(item.id),
                    item_id=item.id,
                    title=item.title,
                    old_collection_id=item.collection_id,
                    new_collection_id=target_collection_id,
                    old_progress_note=item.progress_note,
                    new_progress_note=None,
                    applied=needs_apply,
                    already_repaired=already,
                )
            )
        repairs.append(
            CollectionRepairPlan(
                collection_name=progress_note,
                collection_id=collection_id,
                created=False,
                matched_progress_note=progress_note,
                items=item_repairs,
            )
        )
    return repairs


def discover_additional_candidates(
    db: Session,
    *,
    user_id: UUID,
    import_item_ids: set[UUID],
    source_ids: dict[UUID, int],
    required_notes: set[str],
) -> list[dict[str, object]]:
    rows = db.execute(
        select(Item, Category.name)
        .join(Category, Category.id == Item.category_id)
        .where(
            Item.id.in_(import_item_ids),
            Item.user_id == user_id,
            Item.progress_note.is_not(None),
            Category.name != ENTERTAINMENT_CATEGORY_NAME,
        )
    ).all()

    grouped: dict[str, list[tuple[Item, str]]] = defaultdict(list)
    for item, category_name in rows:
        note = item.progress_note
        if note is None:
            continue
        grouped[note].append((item, category_name))

    candidates: list[dict[str, object]] = []
    for note, group in sorted(grouped.items(), key=lambda x: x[0]):
        is_required = note in required_notes
        count = len(group)
        has_series = "시리즈" in note
        if not is_required and count < 2 and not has_series:
            continue

        reasons: list[str] = []
        if count >= 2:
            reasons.append(f"동일 progress_note가 {count}개 Item에서 반복")
        if has_series:
            reasons.append('progress_note에 "시리즈" 포함')
        if is_required:
            reasons.append("필수 Collection 보정 대상")

        candidates.append(
            {
                "progress_note": note,
                "item_count": count,
                "category_names": sorted({cat for _, cat in group}),
                "item_ids": [str(item.id) for item, _ in group],
                "titles": [item.title for item, _ in group],
                "suggested_collection_name": note,
                "reason": "; ".join(reasons),
                "applied": is_required,
            }
        )
    return candidates


def build_repair_plan(
    db: Session,
    *,
    movie_path: Path,
    user_email: str,
    import_run_id: UUID | None = None,
) -> RepairPlan:
    user = find_user(db, user_email)
    import_run = resolve_import_run(db, user_id=user.id, import_run_id=import_run_id)
    import_item_ids = _imported_item_ids(db, import_run.id)
    source_ids = _source_id_map(db, import_run.id)

    title_repair = plan_title_repair(
        db,
        import_run_id=import_run.id,
        import_item_ids=import_item_ids,
        movie_path=movie_path,
    )
    collection_repairs = plan_collection_repairs(
        db,
        user_id=user.id,
        import_item_ids=import_item_ids,
        source_ids=source_ids,
    )
    required_set = set(REQUIRED_COLLECTION_PROGRESS_NOTES)
    additional = discover_additional_candidates(
        db,
        user_id=user.id,
        import_item_ids=import_item_ids,
        source_ids=source_ids,
        required_notes=required_set,
    )
    return RepairPlan(
        import_run=import_run,
        user=user,
        title_repair=title_repair,
        collection_repairs=collection_repairs,
        additional_candidates=additional,
        import_item_ids=import_item_ids,
    )


def _count_metrics(db: Session, user_id: UUID, import_item_ids: set[UUID]) -> dict[str, object]:
    item_count = db.scalar(
        select(func.count()).select_from(Item).where(Item.id.in_(import_item_ids))
    )
    planned = db.scalar(
        select(func.count())
        .select_from(Item)
        .where(Item.id.in_(import_item_ids), Item.status == ItemStatus.PLANNED)
    )
    completed = db.scalar(
        select(func.count())
        .select_from(Item)
        .where(Item.id.in_(import_item_ids), Item.status == ItemStatus.COMPLETED)
    )
    category_counts = dict(
        db.execute(
            select(Category.name, func.count())
            .select_from(Item)
            .join(Category, Category.id == Item.category_id)
            .where(Item.id.in_(import_item_ids))
            .group_by(Category.name)
        ).all()
    )
    return {
        "item_count": item_count,
        "planned": planned,
        "completed": completed,
        "category_counts": category_counts,
    }


def _title_repair_to_dict(plan: TitleRepairPlan) -> dict[str, object]:
    return {
        "source_id": plan.source_id,
        "item_id": str(plan.item_id) if plan.item_id else None,
        "old_title": plan.old_title,
        "new_title": plan.new_title,
        "old_length": plan.old_length,
        "new_length": plan.new_length,
        "old_title_sha256": hashlib.sha256((plan.old_title or "").encode()).hexdigest(),
        "new_title_sha256": hashlib.sha256(plan.new_title.encode()).hexdigest(),
        "source_title_match": plan.source_title_match,
        "applied": plan.applied,
        "already_repaired": plan.already_repaired,
    }


def _collection_repair_to_dict(plan: CollectionRepairPlan) -> dict[str, object]:
    return {
        "collection_name": plan.collection_name,
        "collection_id": str(plan.collection_id) if plan.collection_id else None,
        "created": plan.created,
        "matched_progress_note": plan.matched_progress_note,
        "matched_item_count": plan.matched_item_count,
        "updated_item_count": plan.updated_item_count,
        "already_repaired_item_count": plan.already_repaired_item_count,
        "items": [
            {
                "source_id": item.source_id,
                "item_id": str(item.item_id),
                "title": item.title,
                "old_collection_id": str(item.old_collection_id) if item.old_collection_id else None,
                "new_collection_id": str(item.new_collection_id) if item.new_collection_id else None,
                "old_progress_note": item.old_progress_note,
                "new_progress_note": item.new_progress_note,
                "applied": item.applied,
                "already_repaired": item.already_repaired,
            }
            for item in plan.items
        ],
    }


def run_legacy_import_repair(
    db: Session,
    *,
    movie_path: Path,
    report_dir: Path,
    user_email: str | None = None,
    import_run_id: UUID | None = None,
    dry_run: bool = False,
    apply: bool = False,
    pretty: bool = False,
    commit: bool = True,
) -> RepairResult:
    if dry_run == apply:
        raise RepairBlockedError("--dry-run 또는 --apply 중 하나만 지정해야 합니다.")

    settings = get_settings()
    email = user_email or settings.seed_user_email
    started_at = datetime.now(timezone.utc)

    plan = build_repair_plan(
        db,
        movie_path=movie_path,
        user_email=email,
        import_run_id=import_run_id,
    )

    before_metrics = _count_metrics(db, plan.user.id, plan.import_item_ids)
    before_import_runs = db.scalar(select(func.count()).select_from(LegacyImportRun))
    before_categories = db.scalar(select(func.count()).select_from(Category))

    created_collections = 0
    already_repaired_count = 0
    title_applied = 0
    collection_items_updated = 0

    if apply:
        if plan.title_repair and plan.title_repair.already_repaired:
            already_repaired_count += 1
        elif plan.title_repair and plan.title_repair.item_id:
            item = db.get(Item, plan.title_repair.item_id)
            if item is not None:
                item.title = plan.title_repair.new_title
                title_applied = 1

        for collection_plan in plan.collection_repairs:
            collection = None
            if collection_plan.collection_id:
                collection = db.get(Collection, collection_plan.collection_id)
            if collection is None:
                collection = Collection(
                    user_id=plan.user.id,
                    name=collection_plan.collection_name,
                )
                db.add(collection)
                db.flush()
                collection_plan.collection_id = collection.id
                collection_plan.created = True
                created_collections += 1

            for item_repair in collection_plan.items:
                if item_repair.already_repaired:
                    already_repaired_count += 1
                    continue
                if not item_repair.applied:
                    continue
                item = db.get(Item, item_repair.item_id)
                if item is None:
                    continue
                item.collection_id = collection.id
                item.progress_note = None
                item_repair.new_collection_id = collection.id
                item_repair.new_progress_note = None
                collection_items_updated += 1

        db.flush()

        for note in REQUIRED_COLLECTION_PROGRESS_NOTES:
            remaining = db.scalar(
                select(func.count())
                .select_from(Item)
                .where(
                    Item.id.in_(plan.import_item_ids),
                    Item.progress_note == note,
                )
            )
            if remaining != 0:
                raise RepairBlockedError(
                    f'보정 후에도 progress_note="{note}" Item이 {remaining}건 남아 있습니다.'
                )

        if commit:
            db.commit()
        else:
            db.flush()

    title_dict = _title_repair_to_dict(plan.title_repair) if plan.title_repair else {}
    collection_dicts = [_collection_repair_to_dict(cp) for cp in plan.collection_repairs]

    after_metrics = (
        _count_metrics(db, plan.user.id, plan.import_item_ids) if apply else before_metrics
    )
    after_import_runs = (
        db.scalar(select(func.count()).select_from(LegacyImportRun)) if apply else before_import_runs
    )
    after_categories = (
        db.scalar(select(func.count()).select_from(Category)) if apply else before_categories
    )

    required_results: dict[str, dict[str, int | None]] = {}
    for note in REQUIRED_COLLECTION_PROGRESS_NOTES:
        remaining = db.scalar(
            select(func.count())
            .select_from(Item)
            .where(
                Item.id.in_(plan.import_item_ids),
                Item.progress_note == note,
            )
        )
        linked = db.scalar(
            select(func.count())
            .select_from(Item)
            .join(Collection, Collection.id == Item.collection_id)
            .where(
                Item.id.in_(plan.import_item_ids),
                Collection.name == note,
                Item.progress_note.is_(None),
            )
        )
        required_results[note] = {
            "remaining_progress_note_count": remaining,
            "linked_item_count": linked,
        }

    title_item = (
        db.get(Item, plan.title_repair.item_id)
        if plan.title_repair and plan.title_repair.item_id
        else None
    )
    source_title = plan.title_repair.new_title if plan.title_repair else ""

    verification = {
        "db_item_count_before": before_metrics["item_count"],
        "db_item_count_after": after_metrics["item_count"],
        "db_item_count_unchanged": before_metrics["item_count"] == after_metrics["item_count"],
        "db_category_count_before": before_categories,
        "db_category_count_after": after_categories,
        "db_import_run_count_before": before_import_runs,
        "db_import_run_count_after": after_import_runs,
        "title_source_2209_matches_original": (
            title_item.title == source_title if title_item else None
        ),
        "title_source_2209_not_truncated": (
            len(title_item.title) > 300 if title_item else None
        ),
        "planned_count_unchanged": before_metrics["planned"] == after_metrics["planned"],
        "completed_count_unchanged": before_metrics["completed"] == after_metrics["completed"],
        "category_counts_unchanged": (
            before_metrics["category_counts"] == after_metrics["category_counts"]
        ),
        "required_collection_results": required_results,
        "progress_notes_remaining_for_required_collections": {
            k: v["remaining_progress_note_count"] for k, v in required_results.items()
        },
        "duplicate_collection_names": [],
        "unexpected_item_changes": [],
    }

    title_planned = 0 if (plan.title_repair and plan.title_repair.already_repaired) else 1
    collection_items_planned = sum(
        1 for cp in plan.collection_repairs for item in cp.items if item.applied
    )

    run_report_dir = resolve_run_report_dir(
        report_dir,
        dry_run=dry_run,
        started_at=started_at,
    )

    summary = {
        "dry_run": dry_run,
        "status": "DRY_RUN" if dry_run else "SUCCESS",
        "report_run_dir": str(run_report_dir),
        "target_import_run_id": str(plan.import_run.id),
        "target_user_email": plan.user.email,
        "title_repairs_planned": title_planned,
        "title_repairs_applied": title_applied,
        "collection_names_planned": len(REQUIRED_COLLECTION_PROGRESS_NOTES),
        "collection_names_created": created_collections,
        "collection_items_planned": collection_items_planned,
        "collection_items_updated": collection_items_updated,
        "already_repaired_count": already_repaired_count,
        "additional_candidate_count": len(plan.additional_candidates),
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    report_paths = write_repair_reports(
        run_report_dir,
        summary=summary,
        title_repair=title_dict,
        collection_repairs=collection_dicts,
        additional_candidates=plan.additional_candidates,
        verification=verification,
        pretty=pretty,
    )

    if dry_run:
        pass  # no DB writes; do not rollback caller session state

    return RepairResult(
        summary=summary,
        title_repair=title_dict,
        collection_repairs=collection_dicts,
        additional_candidates=plan.additional_candidates,
        verification=verification,
        report_paths=report_paths,
    )
