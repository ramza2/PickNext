"""Validate and convert a single legacy movie object (pure, no DB)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.legacy.category_map import map_legacy_category_id
from app.services.legacy.dates import parse_legacy_datetime, to_utc_iso_z
from app.services.legacy.series_classifier import (
    SeriesClassification,
    SeriesClassificationResult,
    classify_series,
)


@dataclass
class ItemConversion:
    source_index: int
    source_id: int | None
    title: str | None
    category_id: int | None
    category_name: str | None
    status: str | None
    rating: float | None
    created_at: str | None
    updated_at: str | None
    classification: SeriesClassificationResult | None
    error_codes: list[str] = field(default_factory=list)
    error_messages: list[str] = field(default_factory=list)
    warning_codes: list[str] = field(default_factory=list)
    warning_messages: list[str] = field(default_factory=list)
    original_data: Any = None
    is_critical: bool = False
    is_convertible: bool = False

    @property
    def has_category_issue(self) -> bool:
        return any(
            code in self.error_codes
            for code in (
                "MISSING_CATEGORY",
                "INVALID_CATEGORY",
                "CATEGORY_MAPPING_FAILED",
            )
        )


def _add_error(result: ItemConversion, code: str, message: str, *, critical: bool = True) -> None:
    result.error_codes.append(code)
    result.error_messages.append(message)
    if critical:
        result.is_critical = True


def _add_warning(result: ItemConversion, code: str, message: str) -> None:
    result.warning_codes.append(code)
    result.warning_messages.append(message)


def convert_legacy_item(
    raw: Any,
    *,
    source_index: int,
    frequency_map: dict[str, int],
    duplicate_ids: set[int],
) -> ItemConversion:
    """Validate and dry-run convert one legacy JSON element."""
    result = ItemConversion(
        source_index=source_index,
        source_id=None,
        title=None,
        category_id=None,
        category_name=None,
        status=None,
        rating=None,
        created_at=None,
        updated_at=None,
        classification=None,
        original_data=raw,
    )

    if not isinstance(raw, dict):
        _add_error(result, "NOT_OBJECT", "항목이 JSON 객체가 아님")
        return result

    # --- id ---
    if "id" not in raw or raw["id"] is None:
        _add_error(result, "MISSING_SOURCE_ID", "원본 id 누락")
    else:
        raw_id = raw["id"]
        if isinstance(raw_id, bool) or not isinstance(raw_id, int):
            _add_error(result, "INVALID_SOURCE_ID", f"원본 id 타입이 정수가 아님: {type(raw_id).__name__}")
        else:
            result.source_id = raw_id
            if raw_id in duplicate_ids:
                _add_error(
                    result,
                    "DUPLICATE_SOURCE_ID",
                    f"원본 id 중복: {raw_id}",
                )

    # --- title / name ---
    if "name" not in raw or raw["name"] is None:
        _add_error(result, "MISSING_TITLE", "제목(name) 누락")
    elif not isinstance(raw["name"], str):
        _add_error(result, "INVALID_TITLE", "제목(name)이 문자열이 아님")
    else:
        title = raw["name"].strip()
        if not title:
            _add_error(result, "EMPTY_TITLE", "제목(name)이 비어 있음")
        else:
            result.title = title

    # --- category ---
    category = raw.get("category")
    if category is None:
        _add_error(result, "MISSING_CATEGORY", "category 누락")
    elif not isinstance(category, dict):
        _add_error(result, "INVALID_CATEGORY", "category가 객체가 아님")
    else:
        cat_id = category.get("id")
        if cat_id is None:
            _add_error(result, "MISSING_CATEGORY", "category.id 누락")
        elif isinstance(cat_id, bool) or not isinstance(cat_id, int):
            _add_error(
                result,
                "INVALID_CATEGORY",
                f"category.id 타입이 정수가 아님: {type(cat_id).__name__}",
            )
        else:
            result.category_id = cat_id
            mapped = map_legacy_category_id(cat_id)
            if mapped is None:
                _add_error(
                    result,
                    "CATEGORY_MAPPING_FAILED",
                    f"Seed 카테고리 매핑 실패: category.id={cat_id}",
                )
            else:
                result.category_name = mapped.name

    # --- haveSeen ---
    if "haveSeen" not in raw:
        _add_error(result, "MISSING_HAVE_SEEN", "haveSeen 누락")
    elif not isinstance(raw["haveSeen"], bool):
        _add_error(
            result,
            "INVALID_HAVE_SEEN",
            f"haveSeen이 Boolean이 아님: {type(raw['haveSeen']).__name__}",
        )
    else:
        result.status = "COMPLETED" if raw["haveSeen"] else "PLANNED"

    # --- starNum / rating ---
    if "starNum" not in raw:
        _add_error(result, "MISSING_RATING", "starNum 누락")
    else:
        star = raw["starNum"]
        if isinstance(star, bool) or not isinstance(star, (int, float)):
            _add_error(
                result,
                "INVALID_RATING_TYPE",
                f"starNum이 숫자가 아님: {type(star).__name__}",
            )
        else:
            try:
                rating = Decimal(str(star))
            except (InvalidOperation, ValueError):
                _add_error(result, "INVALID_RATING_TYPE", f"starNum 파싱 실패: {star!r}")
            else:
                if rating < Decimal("0") or rating > Decimal("5"):
                    _add_error(
                        result,
                        "RATING_OUT_OF_RANGE",
                        f"평점 범위 오류(0.0~5.0): {rating}",
                    )
                else:
                    result.rating = float(rating)

    # --- dates ---
    created_dt = None
    if "registDt" not in raw or raw["registDt"] is None:
        _add_error(result, "MISSING_REGIST_DT", "registDt 누락")
    elif not isinstance(raw["registDt"], str):
        _add_error(result, "INVALID_REGIST_DT", "registDt가 문자열이 아님")
    else:
        try:
            created_dt = parse_legacy_datetime(raw["registDt"])
            result.created_at = to_utc_iso_z(created_dt)
        except (ValueError, TypeError) as exc:
            _add_error(result, "REGIST_DT_PARSE_FAILED", f"등록일 파싱 실패: {exc}")

    if "modifyDt" not in raw or raw["modifyDt"] is None:
        if created_dt is not None:
            result.updated_at = result.created_at
        # Missing modifyDt is allowed (not an error).
    elif not isinstance(raw["modifyDt"], str):
        _add_error(result, "INVALID_MODIFY_DT", "modifyDt가 문자열이 아님", critical=False)
        _add_warning(result, "INVALID_MODIFY_DT", "modifyDt가 문자열이 아님")
        if created_dt is not None:
            result.updated_at = result.created_at
    else:
        try:
            updated_dt = parse_legacy_datetime(raw["modifyDt"])
            result.updated_at = to_utc_iso_z(updated_dt)
        except (ValueError, TypeError) as exc:
            _add_error(result, "MODIFY_DT_PARSE_FAILED", f"수정일 파싱 실패: {exc}")
            if created_dt is not None and result.updated_at is None:
                result.updated_at = result.created_at

    # --- series classification (preserve original; empty is fine) ---
    series_raw = raw.get("series") if "series" in raw else None
    # Only pass string/None into classifier; wrong type → warning + empty classification context
    if series_raw is not None and not isinstance(series_raw, str):
        _add_warning(
            result,
            "INVALID_SERIES_TYPE",
            f"series가 문자열이 아님: {type(series_raw).__name__}",
        )
        classification = classify_series(
            None,
            category_id=result.category_id,
            frequency_map=frequency_map,
        )
    else:
        classification = classify_series(
            series_raw,
            category_id=result.category_id,
            frequency_map=frequency_map,
        )
    result.classification = classification

    result.is_convertible = not result.is_critical and bool(
        result.source_id is not None
        and result.title
        and result.category_name
        and result.status
        and result.rating is not None
        and result.created_at
        and result.updated_at
    )
    return result


def classification_to_preview_fields(
    classification: SeriesClassificationResult,
) -> tuple[str | None, str | None]:
    """Map classification to preview collection_name / progress_note."""
    if classification.result == SeriesClassification.COLLECTION:
        return classification.suggested_collection_name, None
    if classification.result == SeriesClassification.PROGRESS_NOTE:
        return None, classification.suggested_progress_note
    # AMBIGUOUS / EMPTY: do not auto-apply to either field
    return None, None
