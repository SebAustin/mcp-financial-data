"""Tests for ``mcp_financial_data.tools.polygon`` stubs."""

from __future__ import annotations

from datetime import date

import pytest

from mcp_financial_data.tools.polygon import PolygonAggregateBar, fetch_aggregates


def test_aggregate_bar_model_validates_positive_prices() -> None:
    PolygonAggregateBar(
        ticker="AAPL",
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1_000_000.0,
        timestamp_ms=1_700_000_000_000,
    )
    with pytest.raises(ValueError):
        PolygonAggregateBar.model_validate(
            {
                "ticker": "AAPL",
                "open": 0.0,
                "high": 1.0,
                "low": 0.5,
                "close": 0.9,
                "volume": 1.0,
                "timestamp_ms": 1,
            }
        )


@pytest.mark.asyncio
async def test_fetch_aggregates_is_stub() -> None:
    with pytest.raises(NotImplementedError, match=r"prompts/02_edgar_client\.md"):
        await fetch_aggregates(
            "AAPL",
            multiplier=1,
            timespan="day",
            start=date(2025, 1, 1),
            end=date(2025, 12, 31),
        )
