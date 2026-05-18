"""Polygon.io async client.

API reference: https://polygon.io/docs/rest. Implementation in
``prompts/02_edgar_client.md`` follow-on.
"""

from __future__ import annotations

from datetime import date
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

POLYGON_BASE_URL: Final[str] = "https://api.polygon.io"

Timespan = Literal["minute", "hour", "day", "week", "month", "quarter", "year"]


class PolygonConfigError(Exception):
    """Polygon API key missing or invalid."""


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
    """Fetch aggregate bars for ``ticker`` over [start, end].

    See ``prompts/02_edgar_client.md`` (Polygon follow-on subsection).
    """
    _ = (ticker, multiplier, timespan, start, end, adjusted, limit)
    raise NotImplementedError("see prompts/02_edgar_client.md")
