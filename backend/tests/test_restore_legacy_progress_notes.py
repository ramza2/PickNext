"""Tests for Legacy progress_note truncation recovery."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import (
    Category,
    CategoryType,
    Item,
    ItemStatus,
    LegacyImportDisposition,
    LegacyImportItem,
    LegacyImportRun,
    LegacyImportRunStatus,
    User,
)
from app.services.legacy.repair import RepairBlockedError
from app.services.legacy.restore_progress_notes import (
    RestoreStatus,
    restore_legacy_progress_notes,
)


def _long_progress_note(prefix: str = "note") -> str:
    # Digit/range-heavy text that classifies as PROGRESS_NOTE and exceeds 200.
    body = ", ".join(f"{i}~{i + 1}" for i in range(1, 90))
    note = f"{prefix}-{body}"
    assert len(note) > 200
    return note


def _movie_row(*, source_id: int, title: str, series: str) -> dict:
    return {
        "id": source_id,
        "category": {"id": 3, "name": "영화"},
        "name": title,
        "series": series,
        "haveSeen": False,
        "starNum": 3.5,
        "registDt": "2017-03-03T11:37:32+0900",
        "modifyDt": "2026-05-04T20:09:12+0900",
    }


@pytest.fixture
def owner(db: Session) -> User:
    user = User(
        email=f"restore-owner-{uuid4().hex[:8]}@picknext.local",
        display_name="Restore Owner",
        password_hash="hash",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def other_user(db: Session) -> User:
    user = User(
        email=f"restore-other-{uuid4().hex[:8]}@picknext.local",
        display_name="Other",
        password_hash="hash",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _category(db: Session, user: User) -> Category:
    cat = Category(
        user_id=user.id,
        name="영화",
        category_type=CategoryType.MEDIA,
        sort_order=1,
    )
    db.add(cat)
    db.flush()
    return cat


def _item(
    db: Session,
    *,
    user: User,
    category: Category,
    title: str,
    progress_note: str | None,
) -> Item:
    item = Item(
        user_id=user.id,
        category_id=category.id,
        title=title,
        status=ItemStatus.PLANNED,
        rating=Decimal("0.0"),
        progress_note=progress_note,
    )
    db.add(item)
    db.flush()
    return item


def _map_import(
    db: Session,
    *,
    user: User,
    source_id: int,
    item: Item,
) -> None:
    run = LegacyImportRun(
        user_id=user.id,
        source_filename="movie.json",
        source_sha256=uuid4().hex,
        source_total_count=1,
        imported_item_count=1,
        skipped_count=0,
        status=LegacyImportRunStatus.SUCCESS,
    )
    db.add(run)
    db.flush()
    db.add(
        LegacyImportItem(
            import_run_id=run.id,
            item_id=item.id,
            source_id=source_id,
            disposition=LegacyImportDisposition.IMPORTED,
        )
    )
    db.flush()


def test_dry_run_would_update_truncated(
    db: Session, owner: User, tmp_path: Path
) -> None:
    full = _long_progress_note("런닝맨")
    truncated = full[:200]
    category = _category(db, owner)
    item = _item(
        db,
        user=owner,
        category=category,
        title="런닝맨",
        progress_note=truncated,
    )
    _map_import(db, user=owner, source_id=7, item=item)

    movie = tmp_path / "movie.json"
    movie.write_text(
        json.dumps(
            [_movie_row(source_id=7, title="런닝맨", series=full)],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = restore_legacy_progress_notes(
        db,
        movie_path=movie,
        user_email=owner.email,
        dry_run=True,
        apply=False,
        commit=False,
    )
    assert result.source_candidates == 1
    assert result.would_update == 1
    assert result.updated == 0
    assert result.candidates[0].status == RestoreStatus.WOULD_UPDATE
    assert db.get(Item, item.id).progress_note == truncated


def test_apply_restores_truncated(db: Session, owner: User, tmp_path: Path) -> None:
    full = _long_progress_note("아는형님")
    truncated = full[:200]
    category = _category(db, owner)
    item = _item(
        db,
        user=owner,
        category=category,
        title="아는 형님",
        progress_note=truncated,
    )
    _map_import(db, user=owner, source_id=18, item=item)
    movie = tmp_path / "movie.json"
    movie.write_text(
        json.dumps(
            [_movie_row(source_id=18, title="아는 형님", series=full)],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = restore_legacy_progress_notes(
        db,
        movie_path=movie,
        user_email=owner.email,
        dry_run=False,
        apply=True,
        commit=False,
    )
    assert result.updated == 1
    assert result.candidates[0].status == RestoreStatus.UPDATED
    assert db.get(Item, item.id).progress_note == full


def test_already_full_is_noop(db: Session, owner: User, tmp_path: Path) -> None:
    full = _long_progress_note("이미복구")
    category = _category(db, owner)
    item = _item(
        db,
        user=owner,
        category=category,
        title="이미복구",
        progress_note=full,
    )
    _map_import(db, user=owner, source_id=99, item=item)
    movie = tmp_path / "movie.json"
    movie.write_text(
        json.dumps(
            [_movie_row(source_id=99, title="이미복구", series=full)],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = restore_legacy_progress_notes(
        db,
        movie_path=movie,
        user_email=owner.email,
        dry_run=False,
        apply=True,
        commit=False,
    )
    assert result.already_full == 1
    assert result.updated == 0
    assert db.get(Item, item.id).progress_note == full


def test_user_edited_conflict_blocks_apply(
    db: Session, owner: User, tmp_path: Path
) -> None:
    full = _long_progress_note("수정됨")
    category = _category(db, owner)
    item = _item(
        db,
        user=owner,
        category=category,
        title="수정됨",
        progress_note="사용자가 바꾼 노트",
    )
    _map_import(db, user=owner, source_id=55, item=item)
    movie = tmp_path / "movie.json"
    movie.write_text(
        json.dumps(
            [_movie_row(source_id=55, title="수정됨", series=full)],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = restore_legacy_progress_notes(
        db,
        movie_path=movie,
        user_email=owner.email,
        dry_run=False,
        apply=True,
        commit=False,
    )
    assert result.blocked is True
    assert result.conflicts == 1
    assert result.updated == 0
    assert db.get(Item, item.id).progress_note == "사용자가 바꾼 노트"


def test_missing_mapping_not_updated(
    db: Session, owner: User, tmp_path: Path
) -> None:
    full = _long_progress_note("매핑없음")
    movie = tmp_path / "movie.json"
    movie.write_text(
        json.dumps(
            [_movie_row(source_id=77, title="매핑없음", series=full)],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    result = restore_legacy_progress_notes(
        db,
        movie_path=movie,
        user_email=owner.email,
        dry_run=False,
        apply=True,
        commit=False,
    )
    assert result.missing_mapping == 1
    assert result.blocked is True
    assert result.updated == 0


def test_other_user_item_not_updated(
    db: Session, owner: User, other_user: User, tmp_path: Path
) -> None:
    full = _long_progress_note("타유저")
    truncated = full[:200]
    other_cat = _category(db, other_user)
    other_item = _item(
        db,
        user=other_user,
        category=other_cat,
        title="타유저",
        progress_note=truncated,
    )
    # Forge a SUCCESS mapping row under owner that points at other user's item.
    # Recovery must refuse WRONG_USER and not modify the foreign item.
    run = LegacyImportRun(
        user_id=owner.id,
        source_filename="movie.json",
        source_sha256=uuid4().hex,
        source_total_count=1,
        imported_item_count=1,
        skipped_count=0,
        status=LegacyImportRunStatus.SUCCESS,
    )
    db.add(run)
    db.flush()
    db.add(
        LegacyImportItem(
            import_run_id=run.id,
            item_id=other_item.id,
            source_id=88,
            disposition=LegacyImportDisposition.IMPORTED,
        )
    )
    db.flush()

    movie = tmp_path / "movie.json"
    movie.write_text(
        json.dumps(
            [_movie_row(source_id=88, title="타유저", series=full)],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    result = restore_legacy_progress_notes(
        db,
        movie_path=movie,
        user_email=owner.email,
        dry_run=False,
        apply=True,
        commit=False,
    )
    assert result.wrong_user == 1
    assert result.blocked is True
    assert db.get(Item, other_item.id).progress_note == truncated


def test_ambiguous_source_mapping_blocks(
    db: Session, owner: User, tmp_path: Path
) -> None:
    full = _long_progress_note("모호")
    truncated = full[:200]
    category = _category(db, owner)
    item_a = _item(
        db, user=owner, category=category, title="모호A", progress_note=truncated
    )
    item_b = _item(
        db, user=owner, category=category, title="모호B", progress_note=truncated
    )
    for item in (item_a, item_b):
        _map_import(db, user=owner, source_id=42, item=item)

    movie = tmp_path / "movie.json"
    movie.write_text(
        json.dumps(
            [_movie_row(source_id=42, title="모호", series=full)],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    result = restore_legacy_progress_notes(
        db,
        movie_path=movie,
        user_email=owner.email,
        dry_run=False,
        apply=True,
        commit=False,
    )
    assert result.ambiguous_mapping == 1
    assert result.blocked is True
    assert db.get(Item, item_a.id).progress_note == truncated
    assert db.get(Item, item_b.id).progress_note == truncated


def test_mode_mutex_required(db: Session, owner: User, tmp_path: Path) -> None:
    movie = tmp_path / "movie.json"
    movie.write_text("[]", encoding="utf-8")
    with pytest.raises(RepairBlockedError):
        restore_legacy_progress_notes(
            db,
            movie_path=movie,
            user_email=owner.email,
            dry_run=True,
            apply=True,
        )
