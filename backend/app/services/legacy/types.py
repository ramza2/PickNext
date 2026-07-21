"""Result dataclasses for legacy dry-run analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.legacy.series_classifier import Confidence, SeriesClassification


@dataclass
class InvalidItemRecord:
    source_id: int | None
    source_index: int
    title: str | None
    error_codes: list[str]
    error_messages: list[str]
    original_data: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_index": self.source_index,
            "title": self.title,
            "error_codes": self.error_codes,
            "error_messages": self.error_messages,
            "original_data": self.original_data,
        }


@dataclass
class MissingCategoryRecord:
    source_id: int | None
    source_index: int
    title: str | None
    category_raw: Any
    error_codes: list[str]
    error_messages: list[str]
    original_data: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_index": self.source_index,
            "title": self.title,
            "category_raw": self.category_raw,
            "error_codes": self.error_codes,
            "error_messages": self.error_messages,
            "original_data": self.original_data,
        }


@dataclass
class DuplicateTitleRecord:
    source_id: int | None
    source_index: int
    category_id: int | None
    category_name: str | None
    title: str
    duplicate_group_size: int


@dataclass
class SeriesCandidateRow:
    source_id: int | None
    category_id: int | None
    category_name: str | None
    title: str | None
    original_series: str
    suggested_name: str | None
    confidence: Confidence | None
    reason: str
    kind: SeriesClassification


@dataclass
class NormalizedPreview:
    source_id: int | None
    category_name: str | None
    title: str
    status: str
    rating: float
    collection_name: str | None
    progress_note: str | None
    memo: None
    created_at: str
    updated_at: str
    classification: dict[str, Any]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "category_name": self.category_name,
            "title": self.title,
            "status": self.status,
            "rating": self.rating,
            "collection_name": self.collection_name,
            "progress_note": self.progress_note,
            "memo": self.memo,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "classification": self.classification,
            "warnings": self.warnings,
        }


@dataclass
class AnalysisSummary:
    total_read: int = 0
    valid_json_objects: int = 0
    convertible: int = 0
    critical_errors: int = 0
    warnings: int = 0
    missing_title: int = 0
    missing_source_id: int = 0
    duplicate_source_ids: int = 0
    missing_category: int = 0
    category_mapping_failed: int = 0
    regist_dt_parse_failed: int = 0
    modify_dt_parse_failed: int = 0
    rating_out_of_range: int = 0
    planned: int = 0
    completed: int = 0
    collection_candidates: int = 0
    progress_note_candidates: int = 0
    ambiguous: int = 0
    empty_series: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "total_read": self.total_read,
            "valid_json_objects": self.valid_json_objects,
            "convertible": self.convertible,
            "critical_errors": self.critical_errors,
            "warnings": self.warnings,
            "missing_title": self.missing_title,
            "missing_source_id": self.missing_source_id,
            "duplicate_source_ids": self.duplicate_source_ids,
            "missing_category": self.missing_category,
            "category_mapping_failed": self.category_mapping_failed,
            "regist_dt_parse_failed": self.regist_dt_parse_failed,
            "modify_dt_parse_failed": self.modify_dt_parse_failed,
            "rating_out_of_range": self.rating_out_of_range,
            "planned": self.planned,
            "completed": self.completed,
            "collection_candidates": self.collection_candidates,
            "progress_note_candidates": self.progress_note_candidates,
            "ambiguous": self.ambiguous,
            "empty_series": self.empty_series,
        }


@dataclass
class AnalysisResult:
    summary: AnalysisSummary
    invalid_items: list[InvalidItemRecord] = field(default_factory=list)
    missing_category: list[MissingCategoryRecord] = field(default_factory=list)
    duplicate_source_ids: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    duplicate_titles: list[DuplicateTitleRecord] = field(default_factory=list)
    collection_candidates: list[SeriesCandidateRow] = field(default_factory=list)
    progress_note_candidates: list[SeriesCandidateRow] = field(default_factory=list)
    ambiguous_series: list[SeriesCandidateRow] = field(default_factory=list)
    normalized_preview: list[NormalizedPreview] = field(default_factory=list)
