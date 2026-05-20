"""Integration: MCP Apps UI registration (skipped by default; no Anthropic call)."""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp import Client

from mcp_financial_data.apps.ui import (
    TENK_SUMMARY_CARD_ID,
    TENK_SUMMARY_CARD_RESOURCE_URI,
    TenKSummaryCardProps,
    render_tenk_summary_card,
)
from mcp_financial_data.evals.fixtures import get_offline_fixture
from mcp_financial_data.extractors.tenk import ExtractionResult, TenKSection
from mcp_financial_data.server import TenKExtractOutput, build_app


@pytest.mark.integration
@pytest.mark.asyncio
async def test_build_app_lists_tenk_tool_with_ui_meta() -> None:
    """FastMCP advertises ``tenk.extract_section`` with a UI resource URI."""
    app = build_app()
    async with Client(app) as client:
        tools = await client.list_tools()
    tenk_tools = [t for t in tools if t.name == "tenk.extract_section"]
    assert len(tenk_tools) == 1
    tool = tenk_tools[0]
    meta = getattr(tool, "meta", None) or {}
    ui_meta = meta.get("ui") if isinstance(meta, dict) else None
    assert ui_meta is not None
    assert ui_meta.get("resourceUri") == TENK_SUMMARY_CARD_RESOURCE_URI


@pytest.mark.integration
@pytest.mark.asyncio
async def test_call_tenk_extract_section_ships_ui_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FastMCP client call returns extraction + MCP Apps UI envelope (mocked extractor)."""
    extraction = ExtractionResult.model_validate(get_offline_fixture("tenk-aapl-risk-factors"))

    async def _fake_extract(
        section: TenKSection,
        **kwargs: Any,
    ) -> ExtractionResult:
        _ = (section, kwargs)
        return extraction

    monkeypatch.setattr(
        "mcp_financial_data.server.extract_tenk_section",
        _fake_extract,
    )

    section = TenKSection(
        section="item_1a_risk_factors",
        document_title="AAPL 10-K FY2025 Item 1A",
        text="The Company's business depends on supply chain partners.",
    )
    app = build_app()
    async with Client(app) as client:
        result = await client.call_tool(
            "tenk.extract_section",
            {
                "section": section.model_dump(mode="json"),
                "cik": "0000320193",
                "company_name": "Apple Inc.",
            },
        )

    assert result.is_error is False
    assert isinstance(result.data, TenKExtractOutput)
    assert result.data.ui["id"] == TENK_SUMMARY_CARD_ID
    assert len(result.data.ui["citationPills"]) >= 2
    assert result.data.extraction.latency_ms == 0.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_tenk_summary_card_resource() -> None:
    """``resources/read`` serves the HTML shell for the MCP Apps resource URI."""
    app = build_app()
    async with Client(app) as client:
        contents = await client.read_resource(TENK_SUMMARY_CARD_RESOURCE_URI)
    assert len(contents) >= 1
    text = getattr(contents[0], "text", None) or ""
    assert "tenk-summary-card-root" in text
    assert "tenk-summary-card.bundle.js" in text


@pytest.mark.integration
def test_render_envelope_for_offline_fixture() -> None:
    """Offline fixture produces a valid UI envelope without network."""
    extraction = ExtractionResult.model_validate(get_offline_fixture("tenk-aapl-risk-factors"))
    envelope = render_tenk_summary_card(
        TenKSummaryCardProps(
            extraction=extraction,
            cik="0000320193",
            company_name="Apple Inc.",
        )
    )
    assert envelope["id"] == TENK_SUMMARY_CARD_ID
    assert envelope["citationPills"]
