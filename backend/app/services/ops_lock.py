"""Process-local database maintenance lock (single Uvicorn worker assumption)."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class MaintenanceState:
    active: bool = False
    reason: str | None = None
    started_at: datetime | None = None


_lock = threading.RLock()
_busy = False
_state = MaintenanceState()


def try_acquire_ops_lock() -> bool:
    with _lock:
        global _busy
        if _busy:
            return False
        _busy = True
        return True


def release_ops_lock() -> None:
    with _lock:
        global _busy
        _busy = False


def set_maintenance(active: bool, reason: str | None = None) -> None:
    with _lock:
        _state.active = active
        _state.reason = reason if active else None
        _state.started_at = datetime.now(timezone.utc) if active else None


def is_maintenance() -> bool:
    with _lock:
        return _state.active


def is_ops_busy() -> bool:
    with _lock:
        return _busy
