"""Pytest fixtures for the unit test suite.

- ``set_test_env`` autouse: seeds a sane minimal environment before
  ``Settings`` is materialized for the first time in any test.
- ``settings`` fixture: returns a freshly reloaded Settings.
- ``respx_mock`` fixture: provided by the respx package via ``pytest_plugins``.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest_plugins = ("respx",)


@pytest.fixture(autouse=True)
def set_test_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Set deterministic env vars so Settings has predictable defaults in tests.

    Reloads ``Settings`` after env mutation so tests get a fresh cached value.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("FRED_API_KEY", "test-fred-key")
    monkeypatch.setenv("POLYGON_API_KEY", "test-polygon-key")
    monkeypatch.setenv("EDGAR_USER_AGENT", "Test Suite <test@example.com>")
    monkeypatch.setenv("EDGAR_RATE_LIMIT_PER_SEC", "10")
    monkeypatch.setenv("MCP_OAUTH_ISSUER", "https://idp.local.test")
    monkeypatch.setenv("MCP_OAUTH_AUDIENCE", "mcp-financial-data")
    monkeypatch.setenv("MCP_OAUTH_JWKS_URL", "https://idp.local.test/.well-known/jwks.json")
    monkeypatch.setenv("MCP_OAUTH_REQUIRED_SCOPES", "mcp:read mcp:tools")
    monkeypatch.setenv("MAX_API_SPEND_USD", "50")
    monkeypatch.setenv("EVAL_OFFLINE", "1")
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    from mcp_financial_data.settings import reload_settings

    reload_settings()
    yield
    reload_settings()


@pytest.fixture
def settings() -> object:
    """Return a freshly-reloaded Settings using the autouse env."""
    from mcp_financial_data.settings import reload_settings

    return reload_settings()
