"""Tests for ``mcp_financial_data.tools.polygon``."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from mcp_financial_data.tools import polygon as polygon_mod
from mcp_financial_data.tools.cache import SqliteCache
from mcp_financial_data.tools.polygon import (
    PolygonAggregateBar,
    PolygonConfigError,
    fetch_aggregates,
)


@pytest.fixture(autouse=True)
def _isolated_polygon_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = SqliteCache(path=tmp_path / "polygon_test_cache.sqlite")
    monkeypatch.setattr(polygon_mod, "_DEFAULT_CACHE", store, raising=False)


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
async def test_fetch_aggregates_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    from mcp_financial_data.settings import reload_settings

    reload_settings()
    with pytest.raises(PolygonConfigError, match="POLYGON_API_KEY"):
        await fetch_aggregates(
            "AAPL",
            multiplier=1,
            timespan="day",
            start=date(2025, 1, 1),
            end=date(2025, 1, 31),
        )


def _aggregates_body_aapl() -> dict[str, object]:
    return {
        "ticker": "AAPL",
        "status": "OK",
        "resultsCount": 2,
        "results": [
            {
                "v": 1_000_000,
                "vw": 100.5,
                "o": 100.0,
                "c": 101.0,
                "h": 102.0,
                "l": 99.0,
                "t": 1_700_000_000_000,
                "n": 5_000,
            },
            {
                "v": 750_000,
                "vw": 101.2,
                "o": 101.0,
                "c": 102.5,
                "h": 103.0,
                "l": 100.5,
                "t": 1_700_086_400_000,
                "n": 4_200,
            },
        ],
    }


@pytest.mark.asyncio
async def test_fetch_aggregates_parses_results() -> None:
    url = "https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2025-01-01/2025-01-31"
    with respx.mock(assert_all_called=True) as mock:
        mock.get(url).mock(return_value=httpx.Response(200, json=_aggregates_body_aapl()))
        bars = await fetch_aggregates(
            "AAPL",
            multiplier=1,
            timespan="day",
            start=date(2025, 1, 1),
            end=date(2025, 1, 31),
        )
    assert len(bars) == 2
    first = bars[0]
    assert first.ticker == "AAPL"
    assert first.open == 100.0
    assert first.close == 101.0
    assert first.high == 102.0
    assert first.low == 99.0
    assert first.volume == 1_000_000
    assert first.vwap == 100.5
    assert first.timestamp_ms == 1_700_000_000_000
    assert first.transactions == 5_000


@pytest.mark.asyncio
async def test_fetch_aggregates_sends_bearer_authorization() -> None:
    url = "https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2025-01-01/2025-01-31"
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get(url).mock(return_value=httpx.Response(200, json=_aggregates_body_aapl()))
        await fetch_aggregates(
            "AAPL",
            multiplier=1,
            timespan="day",
            start=date(2025, 1, 1),
            end=date(2025, 1, 31),
        )
    sent = route.calls.last.request
    assert sent.headers["authorization"].startswith("Bearer ")


@pytest.mark.asyncio
async def test_fetch_aggregates_threads_adjusted_and_limit_into_query() -> None:
    url = "https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2025-01-01/2025-01-31"
    captured_params: dict[str, str] = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        captured_params.update(dict(request.url.params))
        return httpx.Response(200, json=_aggregates_body_aapl())

    with respx.mock(assert_all_called=True) as mock:
        mock.get(url).mock(side_effect=_capture)
        await fetch_aggregates(
            "AAPL",
            multiplier=1,
            timespan="day",
            start=date(2025, 1, 1),
            end=date(2025, 1, 31),
            adjusted=False,
            limit=42,
        )
    assert captured_params.get("adjusted") == "false"
    assert captured_params.get("limit") == "42"


@pytest.mark.asyncio
async def test_fetch_aggregates_caches_on_second_call() -> None:
    url = "https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2025-01-01/2025-01-31"
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get(url).mock(return_value=httpx.Response(200, json=_aggregates_body_aapl()))
        await fetch_aggregates(
            "AAPL",
            multiplier=1,
            timespan="day",
            start=date(2025, 1, 1),
            end=date(2025, 1, 31),
        )
        await fetch_aggregates(
            "AAPL",
            multiplier=1,
            timespan="day",
            start=date(2025, 1, 1),
            end=date(2025, 1, 31),
        )
    assert route.call_count == 1
