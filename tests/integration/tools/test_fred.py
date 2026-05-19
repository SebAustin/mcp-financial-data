"""Live FRED round-trip. Skipped by default.

Run with ``make test-int`` after exporting ``FRED_API_KEY``. GDP is the
canonical example used by the prompt-02 acceptance suite.
"""

from __future__ import annotations

from datetime import date

import pytest

from mcp_financial_data.settings import reload_settings
from mcp_financial_data.tools.fred import fetch_series

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_live_fetch_series_gdp_q1_2025() -> None:
    settings = reload_settings()
    if settings.fred_api_key is None:
        pytest.skip("FRED_API_KEY not set")
    series = await fetch_series("GDP", start=date(2025, 1, 1), end=date(2025, 3, 31))
    assert series.series_id == "GDP"
    assert series.frequency.lower().startswith("quarter")
    assert series.observations, "expected at least one GDP observation in 2025-Q1"
    last_obs = series.observations[-1]
    assert last_obs.value is not None
    assert last_obs.value > 0
