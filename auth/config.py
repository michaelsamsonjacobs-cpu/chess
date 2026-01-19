from functools import lru_cache
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration values for the authentication service."""

    database_url: str = Field(
        default="sqlite:///./data/auth.db",
        validation_alias=AliasChoices("AUTH_DATABASE_URL", "DATABASE_URL"),
        description="SQLAlchemy database URL.",
    )
    jwt_secret_key: str = Field(
        default="",
        validation_alias=AliasChoices("AUTH_JWT_SECRET", "JWT_SECRET"),
        description="Secret key used to sign JWT tokens.",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        validation_alias=AliasChoices("AUTH_JWT_ALGORITHM", "JWT_ALGORITHM"),
    )
    access_token_expire_minutes: int = Field(
        default=60 * 24,
        validation_alias=AliasChoices("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "ACCESS_TOKEN_EXPIRE_MINUTES"),
        description="Expiration of access tokens in minutes.",
    )
    tls_cert_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AUTH_TLS_CERT_PATH", "TLS_CERT_PATH"),
    )
    tls_key_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AUTH_TLS_KEY_PATH", "TLS_KEY_PATH"),
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.jwt_secret_key:
        raise RuntimeError(
            "AUTH_JWT_SECRET must be provided via environment variables or a vault-managed secret."
        )
    return settings
