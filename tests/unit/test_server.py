"""Tests for ``mcp_financial_data.server``."""

from __future__ import annotations

import pytest

from mcp_financial_data.server import (
    SERVER_NAME,
    CompanyFactsInput,
    ExtractTenKInput,
    FredSeriesInput,
    ListFilingsInput,
    PolygonAggregatesInput,
    build_app,
)


def test_build_app_smokes() -> None:
    app = build_app()
    assert app is not None
    assert app.name == SERVER_NAME


def test_input_models_reject_extras() -> None:
    with pytest.raises(ValueError):
        ListFilingsInput.model_validate({"cik": "0000320193", "garbage": True})

    with pytest.raises(ValueError):
        CompanyFactsInput.model_validate({"cik": "0000320193", "x": 1})

    with pytest.raises(ValueError):
        FredSeriesInput.model_validate({"series_id": "GDP", "y": 1})


def test_polygon_input_enforces_bounds() -> None:
    with pytest.raises(ValueError):
        PolygonAggregatesInput.model_validate(
            {
                "ticker": "AAPL",
                "multiplier": 0,  # ge=1
                "timespan": "day",
                "start": "2025-01-01",
                "end": "2025-12-31",
            }
        )


def test_extract_tenk_input_requires_section() -> None:
    with pytest.raises(ValueError):
        ExtractTenKInput.model_validate({})
