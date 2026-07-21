"""Parse legacy Android datetime strings."""

from __future__ import annotations

import re
from datetime import datetime, timezone

# Examples: 2017-03-03T11:37:32+0900, 2017-03-03T11:37:32+09:00
_OFFSET_NO_COLON = re.compile(r"([+-]\d{2})(\d{2})$")


def normalize_legacy_datetime_string(value: str) -> str:
    """Normalize +0900-style offsets to ISO-8601 (+09:00)."""
    text = value.strip()
    match = _OFFSET_NO_COLON.search(text)
    if match and ":" not in match.group(0):
        text = text[: match.start()] + f"{match.group(1)}:{match.group(2)}"
    return text


def parse_legacy_datetime(value: str) -> datetime:
    """Parse a legacy datetime, preserving timezone information."""
    normalized = normalize_legacy_datetime_string(value)
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        # Legacy payloads are expected to carry an offset; treat naive as UTC.
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def to_utc_iso_z(value: datetime) -> str:
    """Format datetime as UTC ISO-8601 with Z suffix."""
    utc = value.astimezone(timezone.utc)
    return utc.isoformat().replace("+00:00", "Z")
