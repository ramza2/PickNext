"""Password hashing, session tokens, and verification-code HMAC helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_password_hasher = PasswordHasher()

# Precomputed Argon2id hash of a fixed dummy password for timing equalization.
# Not a real credential; used only when the login_id does not resolve to a user.
_DUMMY_PASSWORD = "picknext-timing-dummy-password-not-a-secret"
DUMMY_PASSWORD_HASH: str = _password_hasher.hash(_DUMMY_PASSWORD)

LOGIN_ID_PATTERN = r"^[a-z0-9][a-z0-9._-]{3,29}$"
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return True only for a valid Argon2id hash match.

    Non-Argon2 hashes (e.g. legacy SHA-256 seed placeholders) never succeed;
    a dummy verify still runs to reduce timing leakage.
    """
    if not password_hash or not password_hash.startswith("$argon2"):
        try:
            _password_hasher.verify(DUMMY_PASSWORD_HASH, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            pass
        return False
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def run_dummy_password_verify(password: str) -> None:
    """Equalize login timing when the account does not exist."""
    try:
        _password_hasher.verify(DUMMY_PASSWORD_HASH, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        pass


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_verification_code(*, pepper: str, purpose: str, email: str, code: str) -> str:
    """HMAC-SHA256 over purpose|email|code using AUTH_CODE_PEPPER."""
    material = f"{purpose}|{email}|{code}".encode("utf-8")
    return hmac.new(pepper.encode("utf-8"), material, hashlib.sha256).hexdigest()


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def normalize_login_id(value: str) -> str:
    return value.strip().lower()


def normalize_email(value: str) -> str:
    return value.strip().lower()
