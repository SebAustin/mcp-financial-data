"""Integration: MCP Apps UI registration (skipped by default; no Anthropic call)."""

from __future__ import annotations

import pytest

from mcp_financial_data.apps.ui import (
    TENK_SUMMARY_CARD_ID,
    TENK_SUMMARY_CARD_RESOURCE_URI,
    TenKSummaryCardProps,
    render_tenk_summary_card,
)
from mcp_financial_data.evals.fixtures import get_offline_fixture
from mcp_financial_data.extractors.tenk import ExtractionResult
from mcp_financial_data.server import build_app


@pytest.mark.integration
@pytest.mark.asyncio
async def test_build_app_lists_tenk_tool_with_ui_meta() -> None:
    """FastMCP advertises ``tenk.extract_section`` with a UI resource URI."""
    app = build_app()
    tools = await app.list_tools()
    tenk_tools = [t for t in tools if t.name == "tenk.extract_section"]
    assert len(tenk_tools) == 1
    tool = tenk_tools[0]
    meta = getattr(tool, "meta", None) or getattr(tool, "_meta", None) or {}
    ui_meta = meta.get("ui") if isinstance(meta, dict) else None
    if ui_meta is not None:
        assert ui_meta.get("resourceUri") == TENK_SUMMARY_CARD_RESOURCE_URI


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
