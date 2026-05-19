"""Live Polygon round-trip. Skipped by default.

Run with ``make test-int`` after exporting ``POLYGON_API_KEY``. Uses a
single AAPL daily bar from a fixed historical date so the test result is
stable across re-runs.
"""

from __future__ import annotations

from datetime import date

import pytest

from mcp_financial_data.settings import reload_settings
from mcp_financial_data.tools.polygon import fetch_aggregates

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_live_fetch_aggregates_aapl_daily_bar() -> None:
    settings = reload_settings()
    if settings.polygon_api_key is None:
        pytest.skip("POLYGON_API_KEY not set")
    bars = await fetch_aggregates(
        "AAPL",
        multiplier=1,
        timespan="day",
        start=date(2024, 12, 27),
        end=date(2024, 12, 27),
    )
    assert bars, "expected at least one daily bar for AAPL 2024-12-27"
    bar = bars[0]
    assert bar.ticker == "AAPL"
    assert bar.open > 0
    assert bar.high >= bar.low
    assert bar.volume >= 0
