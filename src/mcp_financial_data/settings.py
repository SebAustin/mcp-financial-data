"""Process-wide configuration loaded from environment via pydantic-settings.

Single source of truth for every credential / endpoint / cap. Modules import
``get_settings()`` (cached) instead of reading env vars directly so unit tests
can override via ``monkeypatch``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed view of the environment.

    See ``.env.example`` for the full list with explanatory comments.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model_primary: str = Field(
        default="claude-sonnet-4-5-20260301", alias="ANTHROPIC_MODEL_PRIMARY"
    )
    anthropic_model_judge: str = Field(
        default="claude-opus-4-7-20260301", alias="ANTHROPIC_MODEL_JUDGE"
    )

    max_api_spend_usd: float = Field(default=50.0, ge=0.0, alias="MAX_API_SPEND_USD")

    edgar_user_agent: str = Field(default="", alias="EDGAR_USER_AGENT")
    edgar_rate_limit_per_sec: int = Field(default=10, ge=1, le=10, alias="EDGAR_RATE_LIMIT_PER_SEC")

    fred_api_key: SecretStr | None = Field(default=None, alias="FRED_API_KEY")
    polygon_api_key: SecretStr | None = Field(default=None, alias="POLYGON_API_KEY")

    mcp_oauth_issuer: str = Field(default="https://idp.local.test", alias="MCP_OAUTH_ISSUER")
    mcp_oauth_audience: str = Field(default="mcp-financial-data", alias="MCP_OAUTH_AUDIENCE")
    mcp_oauth_jwks_url: str = Field(
        default="https://idp.local.test/.well-known/jwks.json", alias="MCP_OAUTH_JWKS_URL"
    )
    mcp_oauth_required_scopes: str = Field(
        default="mcp:read mcp:tools", alias="MCP_OAUTH_REQUIRED_SCOPES"
    )

    mcp_host: str = Field(default="127.0.0.1", alias="MCP_HOST")
    mcp_port: int = Field(default=8765, ge=1, le=65535, alias="MCP_PORT")

    eval_offline: bool = Field(default=True, alias="EVAL_OFFLINE")
    eval_runs_dir: str = Field(default="evals/runs", alias="EVAL_RUNS_DIR")
    eval_seed: int = Field(default=20260518, alias="EVAL_SEED")

    postgres_dsn: str = Field(
        default="postgresql://mcp:mcp@localhost:5432/mcp_financial_data", alias="POSTGRES_DSN"
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", alias="LOG_LEVEL"
    )
    log_format: Literal["json", "console"] = Field(default="json", alias="LOG_FORMAT")

    @property
    def required_scopes_list(self) -> tuple[str, ...]:
        """Required OAuth scopes split from the space-delimited env var."""
        return tuple(s for s in self.mcp_oauth_required_scopes.split() if s)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide Settings, loaded once and cached."""
    return Settings()


def reload_settings() -> Settings:
    """Force re-read of environment. Use in tests after ``monkeypatch.setenv``."""
    get_settings.cache_clear()
    return get_settings()
