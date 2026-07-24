from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
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

    @field_validator("tmdb_api_key", "tmdb_api_read_access_token", mode="before")
    @classmethod
    def empty_tmdb_secret_as_none(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

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
