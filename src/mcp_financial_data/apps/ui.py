"""MCP Apps inline UI registration.

Per MCP spec 2025-11-25, an MCP server can advertise UI components that the
client renders inline. We expose ONE component for now: ``TenKSummaryCard``,
which renders the structured output of the 10-K extractor with citation
pills. Implementation in ``prompts/04_mcp_apps_ui.md``.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from mcp_financial_data.extractors.tenk import ExtractionResult

TENK_SUMMARY_CARD_ID: Final[str] = "tenk-summary-card"


class TenKSummaryCardProps(BaseModel):
    """Props consumed by the TenKSummaryCard React component."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    extraction: ExtractionResult
    cik: str = Field(..., min_length=1, max_length=10)
    company_name: str = Field(..., min_length=1)


def render_tenk_summary_card(props: TenKSummaryCardProps) -> dict[str, object]:
    """Build the MCP Apps UI message for the TenKSummaryCard.

    Returns a JSON-serializable dict matching the MCP spec's ``ui`` envelope.
    Implementation in ``prompts/04_mcp_apps_ui.md``.
    """
    _ = props
    raise NotImplementedError("see prompts/04_mcp_apps_ui.md")
