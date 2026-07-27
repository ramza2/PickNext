"""Send one SMTP test message (manual ops only — not run in CI).

Usage:
  python -m app.cli.test_smtp --to you@example.com
"""

from __future__ import annotations

import argparse
import sys

from app.core.config import get_settings
from app.services.email import (
    EmailSendError,
    OutgoingEmail,
    SmtpConfigurationError,
    SmtpEmailSender,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PickNext SMTP connectivity test")
    parser.add_argument("--to", required=True, help="Recipient email")
    args = parser.parse_args(argv)

    settings = get_settings()
    sender = SmtpEmailSender(settings)
    message = OutgoingEmail(
        to_email=args.to.strip(),
        subject="[PickNext] SMTP test",
        body_text="PickNext SMTP test message.\n",
    )

    import anyio

    try:
        anyio.run(sender.send, message)
    except SmtpConfigurationError:
        print("SMTP_CONFIGURATION_ERROR", file=sys.stderr)
        return 2
    except EmailSendError as exc:
        code = str(exc) if str(exc).startswith("SMTP_") else "SMTP_SEND_FAILED"
        print(code, file=sys.stderr)
        return 3

    print("SMTP connection: PASS")
    print("SMTP authentication: PASS")
    print("SMTP test mail: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
