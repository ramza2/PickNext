"""Duplicate title selection for legacy import."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.legacy.transformer import ItemConversion


@dataclass(frozen=True)
class DuplicateSelection:
    category_name: str
    title: str
    kept: ItemConversion
    skipped: list[ItemConversion]
    selection_reason: str


def selection_rank(conv: ItemConversion) -> tuple[int, float, str, int]:
    """Higher rank wins. Tie-break: source_id descending."""
    return (
        1 if conv.status == "COMPLETED" else 0,
        conv.rating if conv.rating is not None else 0.0,
        conv.updated_at or "",
        conv.source_id if conv.source_id is not None else 0,
    )


def explain_selection(winner: ItemConversion, loser: ItemConversion) -> str:
    w_rank = selection_rank(winner)
    l_rank = selection_rank(loser)
    if w_rank[0] != l_rank[0]:
        return "COMPLETED 상태 우선"
    if w_rank[1] != l_rank[1]:
        return "평점이 높은 항목 우선"
    if w_rank[2] != l_rank[2]:
        return "updated_at이 최신인 항목 우선"
    return "source_id가 큰 항목 우선"


def pick_duplicate_winner(group: list[ItemConversion]) -> DuplicateSelection:
    if len(group) < 2:
        raise ValueError("duplicate group must contain at least 2 items")
    sorted_group = sorted(group, key=selection_rank, reverse=True)
    kept = sorted_group[0]
    skipped = sorted_group[1:]
    reason = explain_selection(kept, skipped[0])
    assert kept.category_name and kept.title
    return DuplicateSelection(
        category_name=kept.category_name,
        title=kept.title,
        kept=kept,
        skipped=skipped,
        selection_reason=reason,
    )


def record_summary(conv: ItemConversion) -> dict[str, object]:
    return {
        "source_id": conv.source_id,
        "source_index": conv.source_index,
        "status": conv.status,
        "rating": conv.rating,
        "updated_at": conv.updated_at,
    }
