from functools import lru_cache
from typing import Annotated, Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "PickNext"
    app_env: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    sql_echo: bool = False

    api_v1_prefix: str = "/api/v1"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    secret_key: str = "change-me-to-a-long-random-string"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "picknext"
    postgres_user: str = "picknext"
    postgres_password: str = "change-me-picknext-password"
    database_url: str | None = None

    seed_user_email: str = "dev@picknext.local"
    seed_user_display_name: str = "Dev User"
    seed_user_password: str = "dev-password-change-me"

    # Auth session / verification (AUTH_CODE_PEPPER has no insecure default).
    auth_cookie_name: str = "picknext_session"
    auth_session_ttl_hours: int = 12
    auth_remember_ttl_days: int = 30
    auth_code_ttl_minutes: int = 10
    auth_code_resend_seconds: int = 60
    auth_code_max_attempts: int = 5
    auth_code_pepper: SecretStr
    auth_cookie_secure: bool = False

    # SMTP — secrets never logged or returned in API responses.
    smtp_host: str = "smtp.naver.com"
    smtp_port: int = 465
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: str | None = None
    smtp_from_name: str = "PickNext"
    smtp_use_tls: bool = False
    smtp_use_ssl: bool = True
    smtp_timeout_seconds: float = 30.0

    # TMDB — secrets never logged; Read Access Token preferred over API Key.
    tmdb_api_key: SecretStr | None = None
    tmdb_api_read_access_token: SecretStr | None = None
    tmdb_language: str = "ko-KR"
    tmdb_region: str = "KR"
    tmdb_api_base_url: str = "https://api.themoviedb.org/3"
    tmdb_request_timeout_seconds: float = 10.0
    tmdb_configuration_ttl_seconds: int = 86400
    tmdb_status_ttl_seconds: int = 60
    tmdb_poster_size: str = "w500"
    tmdb_backdrop_size: str = "w780"
    tmdb_profile_size: str = "w185"

    # OPS-1 database maintenance (no admin role Migration — env gate only).
    ops_database_maintenance_enabled: bool = False
    ops_maintenance_admin_login_id: str | None = None
    ops_backup_dir: str = "/app/backups"
    ops_backup_retention: int = 5
    ops_backup_max_upload_bytes: int = 1_073_741_824
    ops_restore_token_ttl_seconds: int = 900

    @field_validator("tmdb_api_key", "tmdb_api_read_access_token", "smtp_password", mode="before")
    @classmethod
    def empty_secret_as_none(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator(
        "smtp_username",
        "smtp_from_email",
        "ops_maintenance_admin_login_id",
        mode="before",
    )
    @classmethod
    def empty_str_as_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def validate_smtp_flags(self) -> Self:
        if self.smtp_use_ssl and self.smtp_use_tls:
            raise ValueError("SMTP_USE_SSL and SMTP_USE_TLS cannot both be true")
        if not (1 <= self.smtp_port <= 65535):
            raise ValueError("SMTP_PORT must be between 1 and 65535")
        if self.smtp_timeout_seconds <= 0:
            raise ValueError("SMTP_TIMEOUT_SECONDS must be positive")
        if self.ops_backup_retention < 1:
            raise ValueError("OPS_BACKUP_RETENTION must be >= 1")
        if self.ops_backup_max_upload_bytes < 1_048_576:
            raise ValueError("OPS_BACKUP_MAX_UPLOAD_BYTES must be >= 1MiB")
        if self.ops_restore_token_ttl_seconds < 60:
            raise ValueError("OPS_RESTORE_TOKEN_TTL_SECONDS must be >= 60")
        pepper = self.auth_code_pepper.get_secret_value().strip()
        if len(pepper) < 16:
            raise ValueError("AUTH_CODE_PEPPER must be a long random secret")
        return self

    @property
    def tmdb_auth_mode(self) -> Literal["bearer", "api_key", "none"]:
        if self._secret_nonempty(self.tmdb_api_read_access_token):
            return "bearer"
        if self._secret_nonempty(self.tmdb_api_key):
            return "api_key"
        return "none"

    @staticmethod
    def _secret_nonempty(value: SecretStr | None) -> bool:
        if value is None:
            return False
        return bool(value.get_secret_value().strip())

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                return value
            return [item.strip() for item in text.split(",") if item.strip()]
        return value

    @property
    def sqlalchemy_database_url(self) -> str | URL:
        """Build a DB URL that safely handles passwords with @, :, etc."""
        if self.database_url:
            return self.database_url
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
