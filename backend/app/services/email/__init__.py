"""Email sending Protocol and implementations."""

from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol

import anyio

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OutgoingEmail:
    to_email: str
    subject: str
    body_text: str


class EmailSender(Protocol):
    async def send(self, message: OutgoingEmail) -> None: ...


@dataclass
class FakeEmailSender:
    """In-memory recorder for tests. Never touches SMTP."""

    messages: list[OutgoingEmail] = field(default_factory=list)
    fail_next: bool = False

    async def send(self, message: OutgoingEmail) -> None:
        if self.fail_next:
            self.fail_next = False
            raise EmailSendError("FakeEmailSender forced failure")
        self.messages.append(message)


class EmailSendError(Exception):
    """Raised when outbound email cannot be delivered."""


class SmtpConfigurationError(EmailSendError):
    pass


class SmtpEmailSender:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send(self, message: OutgoingEmail) -> None:
        await anyio.to_thread.run_sync(self._send_sync, message)

    def _send_sync(self, message: OutgoingEmail) -> None:
        settings = self._settings
        if not settings.smtp_host or not settings.smtp_from_email:
            raise SmtpConfigurationError("SMTP is not configured")
        if settings.smtp_use_ssl and settings.smtp_use_tls:
            raise SmtpConfigurationError("SMTP_USE_SSL and SMTP_USE_TLS cannot both be true")

        msg = EmailMessage()
        msg["Subject"] = message.subject
        msg["From"] = (
            f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
            if settings.smtp_from_name
            else settings.smtp_from_email
        )
        msg["To"] = message.to_email
        msg.set_content(message.body_text)

        password = (
            settings.smtp_password.get_secret_value() if settings.smtp_password else ""
        )
        username = settings.smtp_username or ""

        try:
            if settings.smtp_use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(
                    settings.smtp_host,
                    settings.smtp_port,
                    timeout=settings.smtp_timeout_seconds,
                    context=context,
                ) as smtp:
                    if username:
                        smtp.login(username, password)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(
                    settings.smtp_host,
                    settings.smtp_port,
                    timeout=settings.smtp_timeout_seconds,
                ) as smtp:
                    if settings.smtp_use_tls:
                        context = ssl.create_default_context()
                        smtp.starttls(context=context)
                    if username:
                        smtp.login(username, password)
                    smtp.send_message(msg)
        except smtplib.SMTPAuthenticationError as exc:
            logger.warning("SMTP authentication failed")
            raise EmailSendError("SMTP_AUTH_FAILED") from exc
        except TimeoutError as exc:
            logger.warning("SMTP connection timed out")
            raise EmailSendError("SMTP_CONNECTION_TIMEOUT") from exc
        except ssl.SSLError as exc:
            logger.warning("SMTP SSL error")
            raise EmailSendError("SMTP_SSL_ERROR") from exc
        except OSError as exc:
            logger.warning("SMTP connection failed")
            raise EmailSendError("SMTP_SEND_FAILED") from exc
        except smtplib.SMTPException as exc:
            logger.warning("SMTP send failed")
            raise EmailSendError("SMTP_SEND_FAILED") from exc


def build_verification_email(*, purpose_label: str, code: str, ttl_minutes: int) -> tuple[str, str]:
    subject = f"[PickNext] {purpose_label}"
    body = (
        "PickNext\n\n"
        f"{purpose_label}\n\n"
        f"인증번호: {code}\n"
        f"유효시간: {ttl_minutes}분\n\n"
        "본인이 요청하지 않았다면 이 메일을 무시하세요.\n"
    )
    return subject, body


def build_password_changed_email() -> tuple[str, str]:
    subject = "[PickNext] 비밀번호가 변경되었습니다"
    body = (
        "PickNext\n\n"
        "계정 비밀번호가 변경되었습니다.\n\n"
        "본인이 변경하지 않았다면 즉시 비밀번호를 재설정하세요.\n"
    )
    return subject, body
