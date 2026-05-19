"""Polygon.io async client.

API reference: https://polygon.io/docs/rest.

Endpoint used (no other endpoint requires an ADR before use today since
Polygon's quota is per-key and bounded by their plan):

- ``/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{start}/{end}``

Authentication is via the ``Authorization: Bearer {key}`` header.

Like FRED (per ADR 0006), Polygon responses are cached for 24 h via the
shared :mod:`tools.cache` store, keyed by URL + sorted query params
(excluding the API key). Polygon is NOT gated by the EDGAR rate limiter.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Final, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from mcp_financial_data.logging import get_logger
from mcp_financial_data.settings import Settings, get_settings
from mcp_financial_data.tools.cache import CacheStore, get_default_cache

POLYGON_BASE_URL: Final[str] = "https://api.polygon.io"

Timespan = Literal["minute", "hour", "day", "week", "month", "quarter", "year"]

_HTTP_TIMEOUT_SECONDS: Final[float] = 15.0
_CACHE_TTL_SECONDS: Final[int] = 24 * 60 * 60

_log = get_logger("tools.polygon")


class PolygonConfigError(Exception):
    """Polygon API key missing or invalid."""


class PolygonHTTPError(Exception):
    """Non-retryable HTTP failure from a Polygon endpoint."""


class _RetryablePolygonStatus(Exception):
    """Internal: 429 / 5xx response signal for tenacity retry."""


class PolygonAggregateBar(BaseModel):
    """One OHLCV bar from the Aggregates v2 endpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ticker: str = Field(..., min_length=1, max_length=12)
    open: float = Field(..., gt=0)
    high: float = Field(..., gt=0)
    low: float = Field(..., gt=0)
    close: float = Field(..., gt=0)
    volume: float = Field(..., ge=0)
    vwap: float | None = None
    timestamp_ms: int = Field(..., ge=0)
    transactions: int | None = Field(default=None, ge=0)


_DEFAULT_CACHE: CacheStore = get_default_cache(get_settings())


def _require_api_key(settings: Settings) -> str:
    secret = settings.polygon_api_key
    raw = secret.get_secret_value().strip() if secret is not None else ""
    if not raw:
        raise PolygonConfigError(
            "POLYGON_API_KEY is not set. Get a key at https://polygon.io/dashboard/api-keys"
        )
    return raw


@retry(
    reraise=True,
    retry=retry_if_exception_type((httpx.HTTPError, _RetryablePolygonStatus)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
)
async def _http_get(url: str, params: dict[str, str], *, bearer: str) -> bytes:
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
        resp = await client.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {bearer}", "Accept": "application/json"},
        )
    if resp.status_code == 429 or 500 <= resp.status_code < 600:
        _log.warning("polygon.http.retryable", url=url, status=resp.status_code)
        raise _RetryablePolygonStatus(f"status={resp.status_code} url={url}")
    if resp.status_code >= 400:
        raise PolygonHTTPError(f"Polygon GET {url} failed: {resp.status_code}")
    return resp.content


async def _get_cached(url: str, params: dict[str, str], *, bearer: str) -> bytes:
    """Cache-aware GET keyed by URL + sorted query string."""
    cache_key = url + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    cached = await _DEFAULT_CACHE.get(cache_key)
    if cached is not None:
        _log.info("polygon.cache.hit", url=url)
        return cached
    body = await _http_get(url, params, bearer=bearer)
    await _DEFAULT_CACHE.set(cache_key, body, ttl_seconds=_CACHE_TTL_SECONDS)
    return body


async def fetch_aggregates(
    ticker: str,
    *,
    multiplier: int,
    timespan: Timespan,
    start: date,
    end: date,
    adjusted: bool = True,
    limit: int = 5000,
) -> list[PolygonAggregateBar]:
    """Fetch OHLCV aggregate bars for ``ticker`` over ``[start, end]``."""
    bearer = _require_api_key(get_settings())
    url = (
        f"{POLYGON_BASE_URL}/v2/aggs/ticker/{ticker}/range/"
        f"{multiplier}/{timespan}/{start.isoformat()}/{end.isoformat()}"
    )
    params: dict[str, str] = {
        "adjusted": "true" if adjusted else "false",
        "limit": str(limit),
        "sort": "asc",
    }
    body = await _get_cached(url, params, bearer=bearer)
    data = json.loads(body)
    return _parse_aggregates(ticker, data)


def _parse_aggregates(ticker: str, data: dict[str, Any]) -> list[PolygonAggregateBar]:
    results = data.get("results", [])
    if not isinstance(results, list):
        return []
    out: list[PolygonAggregateBar] = []
    for row in results:
        if not isinstance(row, dict):
            continue
        try:
            out.append(
                PolygonAggregateBar(
                    ticker=ticker,
                    open=float(row["o"]),
                    high=float(row["h"]),
                    low=float(row["l"]),
                    close=float(row["c"]),
                    volume=float(row["v"]),
                    vwap=float(row["vw"]) if "vw" in row else None,
                    timestamp_ms=int(row["t"]),
                    transactions=int(row["n"]) if "n" in row else None,
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out
