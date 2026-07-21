from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
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
