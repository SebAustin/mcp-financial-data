"""Unit tests for MCP Apps ``resources/read`` wiring."""

from __future__ import annotations

import pytest
from fastmcp import Client

from mcp_financial_data.apps.ui import TENK_SUMMARY_CARD_RESOURCE_URI
from mcp_financial_data.server import build_app


@pytest.mark.asyncio
async def test_tenk_summary_card_resource_read() -> None:
    app = build_app()
    async with Client(app) as client:
        resources = await client.list_resources()
        uris = {str(r.uri) for r in resources}
        assert TENK_SUMMARY_CARD_RESOURCE_URI in uris
        contents = await client.read_resource(TENK_SUMMARY_CARD_RESOURCE_URI)
    assert contents
    text = getattr(contents[0], "text", "")
    assert "tenk-summary-card-root" in text
