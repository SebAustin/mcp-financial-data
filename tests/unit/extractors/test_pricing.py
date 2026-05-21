"""Tests for the extractor's pricing table.

ADR 0007 promises that an unmapped model id fails loudly rather than
silently under-billing. This test set pins that contract.
"""

from __future__ import annotations

import pytest

from mcp_financial_data.extractors._pricing import (
    PRICE_TABLE_VERSION,
    ModelPricing,
    UnknownModelPricingError,
    estimate_cost_usd,
    get_model_pricing,
)


def test_price_table_version_is_iso_date() -> None:
    parts = PRICE_TABLE_VERSION.split("-")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_sonnet_pricing_row_present() -> None:
    sonnet = get_model_pricing("claude-sonnet-4-5-20260301")
    assert sonnet.input_per_mtok == 3.00
    assert sonnet.output_per_mtok == 15.00


def test_estimate_cost_matches_sonnet_table() -> None:
    cost = estimate_cost_usd("claude-sonnet-4-5-20260301", input_tokens=1_000_000, output_tokens=0)
    assert cost == pytest.approx(3.00, abs=1e-6)
    cost2 = estimate_cost_usd("claude-sonnet-4-5-20260301", input_tokens=0, output_tokens=1_000_000)
    assert cost2 == pytest.approx(15.00, abs=1e-6)


def test_unknown_model_raises_with_actionable_message() -> None:
    with pytest.raises(UnknownModelPricingError, match=r"add one to extractors/_pricing\.py"):
        get_model_pricing("claude-future-7-1-19990101")


def test_negative_token_count_rejected() -> None:
    p = ModelPricing(input_per_mtok=3.0, output_per_mtok=15.0)
    with pytest.raises(ValueError, match="non-negative"):
        p.cost_usd(input_tokens=-1, output_tokens=0)
    with pytest.raises(ValueError, match="non-negative"):
        p.cost_usd(input_tokens=0, output_tokens=-5)


def test_resolve_api_model_id_maps_portfolio_fixture_ids() -> None:
    from mcp_financial_data.extractors._pricing import resolve_api_model_id

    assert resolve_api_model_id("claude-opus-4-7-20260301") == "claude-opus-4-7"
    assert get_model_pricing("claude-opus-4-7").input_per_mtok == 15.00
