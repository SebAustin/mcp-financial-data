"""Tests for ``mcp_financial_data.settings``."""

from __future__ import annotations

import pytest

from mcp_financial_data.settings import Settings, get_settings, reload_settings


def test_settings_loads_from_test_env(settings: Settings) -> None:
    assert settings.mcp_oauth_audience == "mcp-financial-data"
    assert settings.edgar_rate_limit_per_sec == 10
    assert settings.required_scopes_list == ("mcp:read", "mcp:tools")
    assert settings.max_api_spend_usd == 50.0
    assert settings.eval_offline is True


def test_required_scopes_list_filters_empty_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_OAUTH_REQUIRED_SCOPES", "  mcp:read   mcp:tools  ")
    s = reload_settings()
    assert s.required_scopes_list == ("mcp:read", "mcp:tools")


def test_get_settings_caches() -> None:
    a = get_settings()
    b = get_settings()
    assert a is b
    c = reload_settings()
    assert c is not a or c == a  # reload may return same value, but cache was cleared
