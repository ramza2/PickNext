"""Series field classification: COLLECTION / PROGRESS_NOTE / AMBIGUOUS."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

from app.services.legacy.category_map import is_entertainment_category


class SeriesClassification(str, Enum):
    COLLECTION = "COLLECTION"
    PROGRESS_NOTE = "PROGRESS_NOTE"
    AMBIGUOUS = "AMBIGUOUS"
    EMPTY = "EMPTY"


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass(frozen=True)
class SeriesClassificationResult:
    original_series: str
    result: SeriesClassification
    confidence: Confidence
    reason: str
    suggested_collection_name: str | None = None
    suggested_progress_note: str | None = None


# Digits, ranges, commas, episode/season/date-like tokens.
_PROGRESS_TOKEN = re.compile(
    r"("
    r"\d{1,4}\s*[~～\-–—]\s*\d{1,4}"  # ranges: 1~82, 44-45
    r"|\d{6,8}"  # compact dates: 091109, 20140503
    r"|\d{4}\s*년"  # year expressions
    r"|\d+\s*(회|화|권|시즌|season|ep\.?|episode)"
    r"|\d+"
    r")",
    re.IGNORECASE,
)

_SEPARATORS = re.compile(r"[,，/&]|그리고")
_PURE_SHORT_NUMBER = re.compile(r"^\d{1,3}$")
_HAS_LETTER = re.compile(r"[A-Za-z가-힣]")


def build_series_frequency(series_values: Sequence[str | None]) -> dict[str, int]:
    """Count non-empty trimmed series values."""
    counts: dict[str, int] = {}
    for raw in series_values:
        if raw is None:
            continue
        value = raw.strip()
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts


def _progress_signal_score(series: str) -> tuple[float, list[str]]:
    """Return (0.0–1.0 score, reason fragments) for progress-note likelihood."""
    reasons: list[str] = []
    stripped = series.strip()
    if not stripped:
        return 0.0, reasons

    if _PURE_SHORT_NUMBER.match(stripped):
        reasons.append("짧은 숫자만으로 구성됨")
        return 0.95, reasons

    tokens = _PROGRESS_TOKEN.findall(stripped)
    digit_chars = sum(1 for ch in stripped if ch.isdigit())
    letter_chars = len(_HAS_LETTER.findall(stripped))
    sep_count = len(_SEPARATORS.findall(stripped))
    tilde = any(ch in stripped for ch in "~～-–—")

    score = 0.0
    if tokens:
        # Ratio of matched progress tokens vs length heuristic.
        token_span = sum(len(t if isinstance(t, str) else t[0]) for t in tokens)
        coverage = min(1.0, token_span / max(len(stripped), 1))
        score += 0.35 + 0.45 * coverage
        reasons.append("숫자·회차·날짜 패턴 비중이 높음")

    if sep_count >= 2:
        score += 0.2
        reasons.append("쉼표 등 회차 목록 구분자가 많음")
    elif sep_count == 1 and digit_chars >= 2:
        score += 0.1

    if tilde and digit_chars >= 2:
        score += 0.15
        reasons.append("물결표/범위 표현 포함")

    if digit_chars > 0 and letter_chars == 0 and sep_count >= 1:
        score += 0.25
        reasons.append("문자 없이 숫자 목록 형태")

    if re.search(r"\d{4}\s*년|\d{2}\s*월", stripped):
        score += 0.2
        reasons.append("연·월 진행 표현 포함")

    return min(score, 1.0), reasons


def _looks_like_title(series: str) -> bool:
    stripped = series.strip()
    if not stripped or _PURE_SHORT_NUMBER.match(stripped):
        return False
    progress_score, _ = _progress_signal_score(stripped)
    if progress_score >= 0.55:
        return False
    return bool(_HAS_LETTER.search(stripped))


def classify_series(
    series: str | None,
    *,
    category_id: int | None,
    frequency_map: Mapping[str, int],
) -> SeriesClassificationResult:
    """
    Classify a legacy `series` value without mutating the original string.

    Pure function: same inputs always yield the same result.
    """
    if series is None:
        return SeriesClassificationResult(
            original_series="",
            result=SeriesClassification.EMPTY,
            confidence=Confidence.HIGH,
            reason="series 필드 없음",
        )

    original = series  # preserve exactly, including surrounding whitespace for non-empty
    stripped = series.strip()
    if not stripped:
        return SeriesClassificationResult(
            original_series=original,
            result=SeriesClassification.EMPTY,
            confidence=Confidence.HIGH,
            reason="series가 비어 있음",
        )

    freq = frequency_map.get(stripped, 1)
    progress_score, progress_reasons = _progress_signal_score(stripped)
    entertainment = is_entertainment_category(category_id)

    if entertainment:
        progress_score = min(1.0, progress_score + 0.25)
        progress_reasons = [*progress_reasons, "예능 카테고리라 Progress Note 가능성을 높게 봄"]

    # Progress-note patterns win over frequency (e.g. repeated "1", "3").
    if progress_score >= 0.7:
        confidence = Confidence.HIGH if progress_score >= 0.85 else Confidence.MEDIUM
        reason = "; ".join(progress_reasons) or "회차·진행 정보 패턴"
        return SeriesClassificationResult(
            original_series=original,
            result=SeriesClassification.PROGRESS_NOTE,
            confidence=confidence,
            reason=reason,
            suggested_progress_note=stripped,
        )

    if freq >= 2 and _looks_like_title(stripped) and progress_score < 0.45:
        confidence = Confidence.HIGH if freq >= 3 else Confidence.MEDIUM
        return SeriesClassificationResult(
            original_series=original,
            result=SeriesClassification.COLLECTION,
            confidence=confidence,
            reason=f"동일 series 값이 {freq}개 항목에서 반복됨",
            suggested_collection_name=stripped,
        )

    if freq >= 2 and progress_score >= 0.45:
        return SeriesClassificationResult(
            original_series=original,
            result=SeriesClassification.PROGRESS_NOTE,
            confidence=Confidence.MEDIUM,
            reason="; ".join(
                [
                    *progress_reasons,
                    f"반복({freq})되지만 진행정보 패턴이 더 강함",
                ]
            ),
            suggested_progress_note=stripped,
        )

    if _looks_like_title(stripped) and progress_score < 0.35:
        # Single occurrence: do not over-claim Collection; mark Ambiguous for review.
        if len(stripped) >= 2 and freq == 1:
            return SeriesClassificationResult(
                original_series=original,
                result=SeriesClassification.AMBIGUOUS,
                confidence=Confidence.LOW,
                reason="작품명·시리즈명처럼 보이지만 반복 근거가 없어 확정하지 않음",
            )

    if entertainment and progress_score >= 0.4:
        return SeriesClassificationResult(
            original_series=original,
            result=SeriesClassification.PROGRESS_NOTE,
            confidence=Confidence.MEDIUM,
            reason="; ".join(progress_reasons) or "예능 series를 Progress Note 후보로 분류",
            suggested_progress_note=stripped,
        )

    reason_bits = ["확신하기 어려운 값"]
    if freq == 1:
        reason_bits.append("단일 출현")
    if 0.35 <= progress_score < 0.7:
        reason_bits.append("진행정보 신호가 중간 수준")
    if entertainment:
        reason_bits.append("예능이지만 패턴이 불명확")

    return SeriesClassificationResult(
        original_series=original,
        result=SeriesClassification.AMBIGUOUS,
        confidence=Confidence.LOW,
        reason="; ".join(reason_bits),
    )
