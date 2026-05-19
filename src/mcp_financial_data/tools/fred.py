"""FRED (St. Louis Fed) async client.

API reference: https://fred.stlouisfed.org/docs/api/fred/.

Two endpoints are needed because FRED's ``series/observations`` API does
not return the series's title, frequency, or units:

- ``/fred/series`` — metadata for one ``series_id``.
- ``/fred/series/observations`` — date/value rows for that series.

Both responses are JSON. The literal ``"."`` value in observations is
FRED's sentinel for "missing"; we map it to ``None`` so downstream code
does not parse a non-numeric float.

Like EDGAR (per ADR 0006), FRED GET responses are cached for 24 h via
the shared :mod:`tools.cache` store, keyed by absolute URL including the
query string. FRED is NOT gated by the EDGAR rate limiter — FRED's
quotas live with the operator's API key.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Final

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

FRED_BASE_URL: Final[str] = "https://api.stlouisfed.org/fred"

_HTTP_TIMEOUT_SECONDS: Final[float] = 15.0
_CACHE_TTL_SECONDS: Final[int] = 24 * 60 * 60

_log = get_logger("tools.fred")


class FredConfigError(Exception):
    """FRED API key missing or invalid."""


class FredHTTPError(Exception):
    """Non-retryable HTTP failure from a FRED endpoint."""


class _RetryableFredStatus(Exception):
    """Internal: 429 / 5xx response signal for tenacity retry."""


class FredObservation(BaseModel):
    """One observation from a FRED series."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    series_id: str = Field(..., min_length=1, max_length=64)
    observation_date: date
    value: float | None = Field(default=None, description="None if FRED returned '.'.")


class FredSeries(BaseModel):
    """Metadata + observations for a single FRED series."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    series_id: str = Field(..., min_length=1, max_length=64)
    title: str
    frequency: str = Field(..., description="e.g. 'Monthly', 'Quarterly'.")
    units: str
    observations: tuple[FredObservation, ...] = ()


_DEFAULT_CACHE: CacheStore = get_default_cache(get_settings())


def _require_api_key(settings: Settings) -> str:
    secret = settings.fred_api_key
    raw = secret.get_secret_value().strip() if secret is not None else ""
    if not raw:
        raise FredConfigError(
            "FRED_API_KEY is not set. Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html"
        )
    return raw


@retry(
    reraise=True,
    retry=retry_if_exception_type((httpx.HTTPError, _RetryableFredStatus)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
)
async def _http_get(url: str, params: dict[str, str]) -> bytes:
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
        resp = await client.get(url, params=params)
    if resp.status_code == 429 or 500 <= resp.status_code < 600:
        _log.warning("fred.http.retryable", url=url, status=resp.status_code)
        raise _RetryableFredStatus(f"status={resp.status_code} url={url}")
    if resp.status_code >= 400:
        raise FredHTTPError(f"FRED GET {url} failed: {resp.status_code}")
    return resp.content


async def _get_cached(url: str, params: dict[str, str]) -> bytes:
    """Cache-aware GET keyed by URL + sorted query string (excluding api_key)."""
    safe_params = {k: v for k, v in sorted(params.items()) if k != "api_key"}
    cache_key = url + "?" + "&".join(f"{k}={v}" for k, v in safe_params.items())
    cached = await _DEFAULT_CACHE.get(cache_key)
    if cached is not None:
        _log.info("fred.cache.hit", url=url)
        return cached
    body = await _http_get(url, params)
    await _DEFAULT_CACHE.set(cache_key, body, ttl_seconds=_CACHE_TTL_SECONDS)
    return body


async def fetch_series(
    series_id: str,
    *,
    start: date | None = None,
    end: date | None = None,
) -> FredSeries:
    """Fetch a FRED series with optional date window.

    Args:
        series_id: FRED series identifier (e.g. ``"GDP"``).
        start: Inclusive lower bound on observation date.
        end: Inclusive upper bound on observation date.

    Maps FRED's ``"."`` missing-value sentinel in observations to ``None``.
    """
    api_key = _require_api_key(get_settings())

    meta_url = f"{FRED_BASE_URL}/series"
    meta_params: dict[str, str] = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
    }
    meta_body = await _get_cached(meta_url, meta_params)
    meta = _parse_series_metadata(series_id, json.loads(meta_body))

    obs_url = f"{FRED_BASE_URL}/series/observations"
    obs_params: dict[str, str] = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
    }
    if start is not None:
        obs_params["observation_start"] = start.isoformat()
    if end is not None:
        obs_params["observation_end"] = end.isoformat()
    obs_body = await _get_cached(obs_url, obs_params)
    observations = _parse_observations(series_id, json.loads(obs_body))

    return FredSeries(
        series_id=series_id,
        title=meta["title"],
        frequency=meta["frequency"],
        units=meta["units"],
        observations=tuple(observations),
    )


def _parse_series_metadata(series_id: str, data: dict[str, Any]) -> dict[str, str]:
    seriess = data.get("seriess", [])
    if not isinstance(seriess, list) or not seriess:
        raise FredHTTPError(f"FRED metadata response missing series for {series_id!r}")
    first = seriess[0]
    if not isinstance(first, dict):
        raise FredHTTPError(f"FRED metadata first entry not a dict for {series_id!r}")
    return {
        "title": str(first.get("title", "")),
        "frequency": str(first.get("frequency", "")),
        "units": str(first.get("units", "")),
    }


def _parse_observations(series_id: str, data: dict[str, Any]) -> list[FredObservation]:
    raw = data.get("observations", [])
    if not isinstance(raw, list):
        return []
    out: list[FredObservation] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            value_raw = entry["value"]
            value: float | None = None if value_raw == "." else float(value_raw)
            out.append(
                FredObservation(
                    series_id=series_id,
                    observation_date=date.fromisoformat(str(entry["date"])),
                    value=value,
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out
