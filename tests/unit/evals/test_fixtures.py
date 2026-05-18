"""Tests for ``mcp_financial_data.evals.fixtures``."""

from __future__ import annotations

import pytest

from mcp_financial_data.evals.fixtures import OFFLINE_FIXTURES, get_offline_fixture


def test_all_seed_case_ids_have_fixtures() -> None:
    expected_ids = {
        "edgar-aapl-list-10k-2025",
        "edgar-msft-revenues-fy2025",
        "edgar-googl-list-8k-2025",
        "fred-gdp-q1-2025",
        "tenk-aapl-risk-factors",
    }
    assert expected_ids.issubset(OFFLINE_FIXTURES.keys())


def test_get_offline_fixture_happy_path() -> None:
    fx = get_offline_fixture("edgar-aapl-list-10k-2025")
    assert "filings" in fx
    assert fx["filings"][0]["cik"] == "0000320193"


def test_get_offline_fixture_missing_raises() -> None:
    with pytest.raises(KeyError, match="No offline fixture"):
        get_offline_fixture("does-not-exist")


def test_tenk_fixture_has_citations_per_fact() -> None:
    fx = get_offline_fixture("tenk-aapl-risk-factors")
    facts = fx["facts"]
    assert isinstance(facts, list)
    assert len(facts) >= 1
    for fact in facts:
        assert isinstance(fact, dict)
        citations = fact["citations"]
        assert isinstance(citations, list)
        assert len(citations) >= 1
