"""Tests for ``mcp_financial_data.tools.fred`` stubs."""

from __future__ import annotations

import pytest

from mcp_financial_data.tools.fred import FredObservation, FredSeries, fetch_series


def test_observation_value_can_be_none() -> None:
    o = FredObservation(series_id="GDP", observation_date="2025-01-01", value=None)  # type: ignore[arg-type]
    assert o.value is None


def test_series_model_default_observations_empty() -> None:
    s = FredSeries(
        series_id="GDP",
        title="Gross Domestic Product",
        frequency="Quarterly",
        units="Billions of Chained 2017 Dollars",
    )
    assert s.observations == ()


@pytest.mark.asyncio
async def test_fetch_series_is_stub() -> None:
    with pytest.raises(NotImplementedError, match=r"prompts/02_edgar_client\.md"):
        await fetch_series("GDP")
