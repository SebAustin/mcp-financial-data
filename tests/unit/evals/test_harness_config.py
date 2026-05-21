"""Tests for online eval configuration preflight."""

from __future__ import annotations

from mcp_financial_data.evals.harness import _online_config_errors
from mcp_financial_data.settings import Settings


def test_online_config_errors_lists_missing_edgar_ua() -> None:
    settings = Settings(
        EDGAR_USER_AGENT="",
        FRED_API_KEY="fred-key",
        ANTHROPIC_API_KEY="sk-test",
    )
    errors = _online_config_errors(settings)
    assert any("EDGAR_USER_AGENT" in msg for msg in errors)


def test_online_config_errors_empty_when_configured() -> None:
    settings = Settings(
        EDGAR_USER_AGENT="Test Bot <test@example.com>",
        FRED_API_KEY="fred-key",
        ANTHROPIC_API_KEY="sk-test",
    )
    assert _online_config_errors(settings) == []
