"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "cobalt-workbench"
    app_version: str = "1.0.0"
    environment: str = Field(default="development", pattern="^(development|production)$")
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR)$")

    # Server
    host: str = "0.0.0.0"
    port: int = 8787

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3080"])

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/sessions.db"

    # Keycloak / OIDC
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "cobalt"
    keycloak_client_id: str = "cobalt-backend"
    keycloak_client_secret: Optional[str] = None
    oidc_issuer: Optional[str] = None
    oidc_audience: str = "cobalt-api"
    oidc_jwks_url: Optional[str] = None

    # ACP (Agent Context Protocol)
    acp_enabled: bool = True
    acp_default_window_tokens: int = 100_000
    acp_compression_target_ratio: float = 0.2  # 5x compression
    acp_fold_threshold_tokens: int = 80_000

    # Request body limits (bytes)
    body_limit_receive: int = 100 * 1024 * 1024  # 100 MiB
    body_limit_decoded: int = 200 * 1024 * 1024  # 200 MiB
    body_limit_outbound: int = 100 * 1024 * 1024  # 100 MiB

    # LLM Provider (opt-in, advisory)
    llm_api_key: Optional[str] = None
    llm_provider: str = "openai-compatible"
    llm_model: str = "gpt-4o-mini"
    llm_base_url: Optional[str] = None
    llm_timeout_seconds: float = 30.0


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()