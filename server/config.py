from functools import lru_cache
from pydantic import Field, AnyHttpUrl, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(
        default="sqlite:///./data/server.db",
        validation_alias=AliasChoices("SERVER_DATABASE_URL", "DATABASE_URL"),
    )
    jwt_secret_key: str = Field(
        default="",
        validation_alias=AliasChoices("SERVER_JWT_SECRET", "JWT_SECRET"),
    )
    jwt_algorithm: str = Field(
        default="HS256",
        validation_alias=AliasChoices("SERVER_JWT_ALGORITHM", "JWT_ALGORITHM"),
    )
    auth_service_url: AnyHttpUrl | None = Field(
        default=None,
        validation_alias=AliasChoices("SERVER_AUTH_SERVICE_URL", "AUTH_SERVICE_URL"),
    )
    tls_cert_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SERVER_TLS_CERT_PATH", "TLS_CERT_PATH"),
    )
    tls_key_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SERVER_TLS_KEY_PATH", "TLS_KEY_PATH"),
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.jwt_secret_key:
        raise RuntimeError(
            "SERVER_JWT_SECRET must be provided via environment variables or a vault-managed secret."
        )
    return settings
