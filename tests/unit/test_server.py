"""Tests for ``mcp_financial_data.server``."""

from __future__ import annotations

import httpx
import pytest

from mcp_financial_data.server import (
    SERVER_NAME,
    CompanyFactsInput,
    ExtractTenKInput,
    FredSeriesInput,
    ListFilingsInput,
    PolygonAggregatesInput,
    build_app,
    oauth_middleware,
)
from mcp_financial_data.settings import get_settings

_MCP_HEADERS = {
    "content-type": "application/json",
    "accept": "application/json, text/event-stream",
}
_INIT_BODY = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"},
    },
}


@pytest.mark.asyncio
async def test_http_app_rejects_missing_bearer_with_401() -> None:
    settings = get_settings()
    app = build_app(settings).http_app(
        transport="streamable-http",
        middleware=oauth_middleware(settings),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/mcp", headers=_MCP_HEADERS, json=_INIT_BODY)

    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate", "").startswith('Bearer error="invalid_token"')


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
