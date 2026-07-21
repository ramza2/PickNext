"""Seed category mapping for legacy category.id values."""

from __future__ import annotations

from dataclasses import dataclass

# Legacy category.id → PickNext seed category name (sort_order order).
SEED_CATEGORY_BY_LEGACY_ID: dict[int, str] = {
    1: "애니메이션",
    2: "애니 영화",
    3: "영화",
    4: "한국드라마",
    5: "일본드라마",
    6: "중국드라마",
    7: "미국드라마",
    8: "예능",
    9: "만화책",
    10: "음식",
}

ENTERTAINMENT_CATEGORY_ID = 8


@dataclass(frozen=True)
class CategoryMapping:
    legacy_id: int
    name: str


def map_legacy_category_id(legacy_id: int) -> CategoryMapping | None:
    name = SEED_CATEGORY_BY_LEGACY_ID.get(legacy_id)
    if name is None:
        return None
    return CategoryMapping(legacy_id=legacy_id, name=name)


def is_entertainment_category(legacy_id: int | None) -> bool:
    return legacy_id == ENTERTAINMENT_CATEGORY_ID
