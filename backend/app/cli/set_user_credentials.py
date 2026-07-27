"""Set login_id and Argon2 password for an existing user (interactive).

Usage:
  python -m app.cli.set_user_credentials --email user@example.com

Never pass the password on the command line.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import User
from app.services.auth_service import AuthError, validate_login_id_value, validate_password_value
from datetime import datetime, timezone


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Set PickNext user credentials")
    parser.add_argument("--email", required=True, help="Existing user email")
    args = parser.parse_args(argv)

    email = args.email.strip().lower()
    settings = get_settings()
    _ = settings  # ensure settings load (AUTH_CODE_PEPPER required)

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"User not found for email: {email}", file=sys.stderr)
            return 1

        login_raw = input("login_id: ").strip()
        try:
            login_id = validate_login_id_value(login_raw)
        except AuthError as exc:
            print(exc.message, file=sys.stderr)
            return 1

        other = db.scalar(
            select(User).where(User.login_id == login_id, User.id != user.id)
        )
        if other is not None:
            print("login_id already taken", file=sys.stderr)
            return 1

        password = getpass.getpass("password: ")
        confirm = getpass.getpass("password (confirm): ")
        try:
            validate_password_value(password)
        except AuthError as exc:
            print(exc.message, file=sys.stderr)
            return 1
        if password != confirm:
            print("password confirmation mismatch", file=sys.stderr)
            return 1

        user.login_id = login_id
        user.display_name = user.display_name or login_id
        user.password_hash = hash_password(password)
        user.email_verified_at = datetime.now(timezone.utc)
        user.is_active = True
        db.commit()
        print(f"Credentials updated for user_id={user.id} login_id={login_id}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
