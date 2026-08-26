"""OPS-1 isolated DB integration tests.

Destructive rename/swap tests run only when:
  POSTGRES_DB starts with picknext_ops1_test_
  and OPS1_INTEGRATION=1

Never targets shared local DB name `picknext`.
"""

from __future__ import annotations

import os

import pytest

from app.core.config import get_settings
from app.services import database_maintenance as dm


def _ops1_integration_enabled() -> bool:
    if os.environ.get("OPS1_INTEGRATION", "").strip() != "1":
        return False
    db_name = get_settings().postgres_db
    return db_name.startswith("picknext_ops1_test_")


pytestmark = pytest.mark.skipif(
    not _ops1_integration_enabled(),
    reason="Set OPS1_INTEGRATION=1 and POSTGRES_DB=picknext_ops1_test_* for swap tests",
)


def test_guard_refuses_shared_picknext_name():
    with pytest.raises(RuntimeError):
        dm._assert_safe_aux_db("picknext")


def test_settings_db_is_ops1_prefixed():
    assert get_settings().postgres_db.startswith("picknext_ops1_test_")
