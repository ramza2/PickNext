"""Password hashing and validation tests (AUTH-1)."""

from __future__ import annotations

import hashlib

import pytest

from app.core.security import (
    DUMMY_PASSWORD_HASH,
    hash_password,
    verify_password,
)
from app.services.auth_service import AuthError, validate_password_value

TEST_PASSWORD = "test-password-ok"


def test_hash_password_uses_argon2id() -> None:
    hashed = hash_password(TEST_PASSWORD)
    assert hashed.startswith("$argon2")


def test_verify_password_accepts_correct_password() -> None:
    hashed = hash_password(TEST_PASSWORD)
    assert verify_password(TEST_PASSWORD, hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password(TEST_PASSWORD)
    assert verify_password("wrong-password-value", hashed) is False


def test_hash_does_not_contain_plaintext() -> None:
    hashed = hash_password(TEST_PASSWORD)
    assert TEST_PASSWORD not in hashed


def test_verify_password_rejects_non_argon2_hash() -> None:
    legacy_hash = hashlib.sha256(TEST_PASSWORD.encode("utf-8")).hexdigest()
    assert legacy_hash.startswith("$argon2") is False
    assert verify_password(TEST_PASSWORD, legacy_hash) is False


def test_verify_password_rejects_empty_hash() -> None:
    assert verify_password(TEST_PASSWORD, "") is False


def test_dummy_password_hash_is_argon2() -> None:
    assert DUMMY_PASSWORD_HASH.startswith("$argon2")
    assert verify_password("any-password", DUMMY_PASSWORD_HASH) is False


def test_validate_password_value_accepts_valid_length() -> None:
    assert validate_password_value(TEST_PASSWORD) == TEST_PASSWORD


def test_validate_password_value_rejects_too_short() -> None:
    with pytest.raises(AuthError) as exc_info:
        validate_password_value("short1")
    assert exc_info.value.code == "AUTH_INVALID_PASSWORD"
    assert exc_info.value.status_code == 422


def test_validate_password_value_rejects_too_long() -> None:
    with pytest.raises(AuthError) as exc_info:
        validate_password_value("x" * 129)
    assert exc_info.value.code == "AUTH_INVALID_PASSWORD"
    assert exc_info.value.status_code == 422
