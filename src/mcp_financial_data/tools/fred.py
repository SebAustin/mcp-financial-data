"""FRED (St. Louis Fed) async client.

API reference: https://fred.stlouisfed.org/docs/api/fred/.
Implementation lives in ``prompts/02_edgar_client.md`` follow-on (Issue #2 deps).
"""

from __future__ import annotations

from datetime import date
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

FRED_BASE_URL: Final[str] = "https://api.stlouisfed.org/fred"


class FredConfigError(Exception):
    """FRED API key missing or invalid."""


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


async def fetch_series(
    series_id: str,
    *,
    start: date | None = None,
    end: date | None = None,
) -> FredSeries:
    """Fetch a FRED series with optional date window.

    See ``prompts/02_edgar_client.md`` (FRED follow-on subsection).
    """
    _ = (series_id, start, end)
    raise NotImplementedError("see prompts/02_edgar_client.md")
