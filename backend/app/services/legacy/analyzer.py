"""Orchestrate legacy movie.json dry-run analysis without touching the database."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.services.legacy.category_map import SEED_CATEGORY_BY_LEGACY_ID
from app.services.legacy.series_classifier import (
    SeriesClassification,
    build_series_frequency,
)
from app.services.legacy.transformer import (
    ItemConversion,
    classification_to_preview_fields,
    convert_legacy_item,
)
from app.services.legacy.types import (
    AnalysisResult,
    AnalysisSummary,
    DuplicateTitleRecord,
    InvalidItemRecord,
    MissingCategoryRecord,
    NormalizedPreview,
    SeriesCandidateRow,
)


def load_json_array(path: Path) -> list[Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"최상위 데이터가 배열이 아님: {path}")
    return data


def _find_duplicate_ids(items: list[Any]) -> set[int]:
    seen: set[int] = set()
    duplicates: set[int] = set()
    for raw in items:
        if not isinstance(raw, dict):
            continue
        raw_id = raw.get("id")
        if isinstance(raw_id, int) and not isinstance(raw_id, bool):
            if raw_id in seen:
                duplicates.add(raw_id)
            else:
                seen.add(raw_id)
    return duplicates


def _series_values_for_frequency(items: list[Any]) -> list[str | None]:
    values: list[str | None] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        series = raw.get("series")
        if series is None or isinstance(series, str):
            values.append(series)
        else:
            values.append(None)
    return values


def analyze_legacy_movies(
    input_path: Path,
    *,
    category_input: Path | None = None,
) -> AnalysisResult:
    """
    Analyze legacy movie.json and produce dry-run conversion results.

    This function must never open a database connection or mutate persistent state.
    """
    items = load_json_array(input_path)
    category_check_notes: list[str] = []
    if category_input is not None and category_input.exists():
        category_check_notes.extend(_validate_category_file(category_input))

    duplicate_ids = _find_duplicate_ids(items)
    frequency_map = build_series_frequency(_series_values_for_frequency(items))

    conversions: list[ItemConversion] = []
    for index, raw in enumerate(items):
        conversions.append(
            convert_legacy_item(
                raw,
                source_index=index,
                frequency_map=frequency_map,
                duplicate_ids=duplicate_ids,
            )
        )

    # Duplicate titles within same category (warning only).
    title_groups: dict[tuple[int | None, str], list[ItemConversion]] = defaultdict(list)
    for conv in conversions:
        if conv.title and conv.category_id is not None:
            title_groups[(conv.category_id, conv.title)].append(conv)

    duplicate_title_convs: set[int] = set()
    duplicate_titles: list[DuplicateTitleRecord] = []
    for (cat_id, title), group in title_groups.items():
        if len(group) < 2:
            continue
        for conv in group:
            duplicate_title_convs.add(conv.source_index)
            conv.warning_codes.append("DUPLICATE_TITLE")
            conv.warning_messages.append(
                f"동일 카테고리 내 중복 제목: category_id={cat_id}, title={title!r}"
            )
            duplicate_titles.append(
                DuplicateTitleRecord(
                    source_id=conv.source_id,
                    source_index=conv.source_index,
                    category_id=cat_id,
                    category_name=conv.category_name,
                    title=title,
                    duplicate_group_size=len(group),
                )
            )

    summary = AnalysisSummary(total_read=len(items))
    result = AnalysisResult(summary=summary)

    # Duplicate source id report
    dup_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for conv in conversions:
        if conv.source_id is not None and conv.source_id in duplicate_ids:
            dup_map[str(conv.source_id)].append(
                {
                    "source_id": conv.source_id,
                    "source_index": conv.source_index,
                    "title": conv.title,
                }
            )
    result.duplicate_source_ids = dict(dup_map)

    for conv in conversions:
        if isinstance(conv.original_data, dict):
            summary.valid_json_objects += 1

        if "MISSING_TITLE" in conv.error_codes or "EMPTY_TITLE" in conv.error_codes:
            summary.missing_title += 1
        if "MISSING_SOURCE_ID" in conv.error_codes:
            summary.missing_source_id += 1
        if "DUPLICATE_SOURCE_ID" in conv.error_codes:
            summary.duplicate_source_ids += 1
        if "MISSING_CATEGORY" in conv.error_codes:
            summary.missing_category += 1
        if "CATEGORY_MAPPING_FAILED" in conv.error_codes:
            summary.category_mapping_failed += 1
        if "REGIST_DT_PARSE_FAILED" in conv.error_codes or "MISSING_REGIST_DT" in conv.error_codes:
            summary.regist_dt_parse_failed += 1
        if "MODIFY_DT_PARSE_FAILED" in conv.error_codes:
            summary.modify_dt_parse_failed += 1
        if "RATING_OUT_OF_RANGE" in conv.error_codes:
            summary.rating_out_of_range += 1

        if conv.is_critical:
            summary.critical_errors += 1
            result.invalid_items.append(
                InvalidItemRecord(
                    source_id=conv.source_id,
                    source_index=conv.source_index,
                    title=conv.title,
                    error_codes=list(conv.error_codes),
                    error_messages=list(conv.error_messages),
                    original_data=conv.original_data,
                )
            )

        if conv.has_category_issue:
            result.missing_category.append(
                MissingCategoryRecord(
                    source_id=conv.source_id,
                    source_index=conv.source_index,
                    title=conv.title,
                    category_raw=(
                        conv.original_data.get("category")
                        if isinstance(conv.original_data, dict)
                        else None
                    ),
                    error_codes=[
                        c
                        for c in conv.error_codes
                        if c
                        in (
                            "MISSING_CATEGORY",
                            "INVALID_CATEGORY",
                            "CATEGORY_MAPPING_FAILED",
                        )
                    ],
                    error_messages=[
                        m
                        for c, m in zip(conv.error_codes, conv.error_messages, strict=True)
                        if c
                        in (
                            "MISSING_CATEGORY",
                            "INVALID_CATEGORY",
                            "CATEGORY_MAPPING_FAILED",
                        )
                    ],
                    original_data=conv.original_data,
                )
            )

        if conv.warning_codes:
            summary.warnings += len(conv.warning_codes)

        classification = conv.classification
        if classification is not None:
            if classification.result == SeriesClassification.EMPTY:
                summary.empty_series += 1
            elif classification.result == SeriesClassification.COLLECTION:
                summary.collection_candidates += 1
                result.collection_candidates.append(
                    SeriesCandidateRow(
                        source_id=conv.source_id,
                        category_id=conv.category_id,
                        category_name=conv.category_name,
                        title=conv.title,
                        original_series=classification.original_series,
                        suggested_name=classification.suggested_collection_name,
                        confidence=classification.confidence,
                        reason=classification.reason,
                        kind=SeriesClassification.COLLECTION,
                    )
                )
            elif classification.result == SeriesClassification.PROGRESS_NOTE:
                summary.progress_note_candidates += 1
                result.progress_note_candidates.append(
                    SeriesCandidateRow(
                        source_id=conv.source_id,
                        category_id=conv.category_id,
                        category_name=conv.category_name,
                        title=conv.title,
                        original_series=classification.original_series,
                        suggested_name=classification.suggested_progress_note,
                        confidence=classification.confidence,
                        reason=classification.reason,
                        kind=SeriesClassification.PROGRESS_NOTE,
                    )
                )
            elif classification.result == SeriesClassification.AMBIGUOUS:
                summary.ambiguous += 1
                result.ambiguous_series.append(
                    SeriesCandidateRow(
                        source_id=conv.source_id,
                        category_id=conv.category_id,
                        category_name=conv.category_name,
                        title=conv.title,
                        original_series=classification.original_series,
                        suggested_name=None,
                        confidence=classification.confidence,
                        reason=classification.reason,
                        kind=SeriesClassification.AMBIGUOUS,
                    )
                )

        if not conv.is_convertible or classification is None:
            continue

        summary.convertible += 1
        if conv.status == "PLANNED":
            summary.planned += 1
        elif conv.status == "COMPLETED":
            summary.completed += 1

        collection_name, progress_note = classification_to_preview_fields(classification)
        result.normalized_preview.append(
            NormalizedPreview(
                source_id=conv.source_id,
                category_name=conv.category_name,
                title=conv.title or "",
                status=conv.status or "",
                rating=conv.rating if conv.rating is not None else 0.0,
                collection_name=collection_name,
                progress_note=progress_note,
                memo=None,
                created_at=conv.created_at or "",
                updated_at=conv.updated_at or "",
                classification={
                    "original_series": classification.original_series,
                    "result": classification.result.value,
                    "confidence": classification.confidence.value,
                    "reason": classification.reason,
                },
                warnings=list(conv.warning_messages),
            )
        )

    result.duplicate_titles = duplicate_titles

    # Attach optional category file notes into summary via side channel? Keep silent;
    # CLI can print. Store on result via dynamic attr not needed.
    _ = category_check_notes
    return result


def _validate_category_file(path: Path) -> list[str]:
    notes: list[str] = []
    try:
        categories = load_json_array(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"category 파일 읽기 실패: {exc}"]

    by_id: dict[int, str] = {}
    for raw in categories:
        if not isinstance(raw, dict):
            continue
        cid = raw.get("id")
        name = raw.get("name")
        if isinstance(cid, int) and isinstance(name, str):
            by_id[cid] = name

    for legacy_id, seed_name in SEED_CATEGORY_BY_LEGACY_ID.items():
        actual = by_id.get(legacy_id)
        if actual is None:
            notes.append(f"category.json에 id={legacy_id} 없음 (Seed: {seed_name})")
        elif actual != seed_name:
            notes.append(
                f"category.json id={legacy_id} 이름 불일치: {actual!r} vs Seed {seed_name!r}"
            )
    return notes
