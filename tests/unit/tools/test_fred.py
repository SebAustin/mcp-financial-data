"""Tests for ``mcp_financial_data.tools.fred``.

The FRED client makes two calls: ``/fred/series`` for metadata and
``/fred/series/observations`` for the data points. Both are mocked here
through respx.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from mcp_financial_data.tools import fred as fred_mod
from mcp_financial_data.tools.cache import SqliteCache
from mcp_financial_data.tools.fred import (
    FredConfigError,
    FredObservation,
    FredSeries,
    fetch_series,
)


@pytest.fixture(autouse=True)
def _isolated_fred_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = SqliteCache(path=tmp_path / "fred_test_cache.sqlite")
    monkeypatch.setattr(fred_mod, "_DEFAULT_CACHE", store, raising=False)


def test_observation_value_can_be_none() -> None:
    o = FredObservation(series_id="GDP", observation_date=date(2025, 1, 1), value=None)
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
async def test_fetch_series_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # Use setenv("") so the absence case also covers a blank .env placeholder.
    monkeypatch.setenv("FRED_API_KEY", "")
    from mcp_financial_data.settings import reload_settings

    reload_settings()
    with pytest.raises(FredConfigError, match="FRED_API_KEY"):
        await fetch_series("GDP")


def _series_metadata_body() -> dict[str, object]:
    return {
        "seriess": [
            {
                "id": "GDP",
                "title": "Gross Domestic Product",
                "frequency": "Quarterly",
                "units": "Billions of Dollars",
            }
        ]
    }


def _series_observations_body() -> dict[str, object]:
    return {
        "observations": [
            {"date": "2025-01-01", "value": "28500.0"},
            {"date": "2025-03-31", "value": "28900.0"},
            {"date": "2025-06-30", "value": "."},  # FRED's "missing" sentinel
        ]
    }


@pytest.mark.asyncio
async def test_fetch_series_parses_observations() -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://api.stlouisfed.org/fred/series").mock(
            return_value=httpx.Response(200, json=_series_metadata_body())
        )
        mock.get("https://api.stlouisfed.org/fred/series/observations").mock(
            return_value=httpx.Response(200, json=_series_observations_body())
        )
        series = await fetch_series("GDP")
    assert series.series_id == "GDP"
    assert series.title == "Gross Domestic Product"
    assert series.frequency == "Quarterly"
    assert series.units == "Billions of Dollars"
    assert len(series.observations) == 3
    assert series.observations[2].value is None  # "." -> None per FRED contract
    assert series.observations[1].value == 28_900.0
    assert series.observations[0].observation_date == date(2025, 1, 1)


@pytest.mark.asyncio
async def test_fetch_series_passes_start_end_to_observations() -> None:
    captured: dict[str, str] = {}

    def _capture_obs(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.url.params))
        return httpx.Response(200, json=_series_observations_body())

    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://api.stlouisfed.org/fred/series").mock(
            return_value=httpx.Response(200, json=_series_metadata_body())
        )
        mock.get("https://api.stlouisfed.org/fred/series/observations").mock(
            side_effect=_capture_obs
        )
        await fetch_series("GDP", start=date(2025, 1, 1), end=date(2025, 6, 30))
    assert captured.get("observation_start") == "2025-01-01"
    assert captured.get("observation_end") == "2025-06-30"
    assert captured.get("series_id") == "GDP"
    assert "api_key" in captured


@pytest.mark.asyncio
async def test_fetch_series_caches_both_calls_on_second_invocation() -> None:
    with respx.mock(assert_all_called=True) as mock:
        meta_route = mock.get("https://api.stlouisfed.org/fred/series").mock(
            return_value=httpx.Response(200, json=_series_metadata_body())
        )
        obs_route = mock.get("https://api.stlouisfed.org/fred/series/observations").mock(
            return_value=httpx.Response(200, json=_series_observations_body())
        )
        await fetch_series("GDP")
        await fetch_series("GDP")
    assert meta_route.call_count == 1
    assert obs_route.call_count == 1
