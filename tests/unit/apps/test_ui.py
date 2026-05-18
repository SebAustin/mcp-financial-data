"""Tests for ``mcp_financial_data.apps.ui`` stubs."""

from __future__ import annotations

import pytest

from mcp_financial_data.apps.ui import (
    TENK_SUMMARY_CARD_ID,
    TenKSummaryCardProps,
    render_tenk_summary_card,
)
from mcp_financial_data.extractors.tenk import ExtractionResult


def test_card_id_is_stable() -> None:
    assert TENK_SUMMARY_CARD_ID == "tenk-summary-card"


def test_props_model_rejects_extras() -> None:
    er = ExtractionResult(
        section="item_1_business",
        document_title="AAPL 10-K Item 1",
        model="claude-sonnet-4-5-20260301",
    )
    with pytest.raises(ValueError):
        TenKSummaryCardProps.model_validate(
            {
                "extraction": er.model_dump(),
                "cik": "0000320193",
                "company_name": "Apple Inc.",
                "extra": "bad",
            }
        )


def test_render_tenk_summary_card_is_stub() -> None:
    er = ExtractionResult(
        section="item_1_business",
        document_title="AAPL 10-K Item 1",
        model="claude-sonnet-4-5-20260301",
    )
    props = TenKSummaryCardProps(extraction=er, cik="0000320193", company_name="Apple Inc.")
    with pytest.raises(NotImplementedError, match=r"prompts/04_mcp_apps_ui\.md"):
        render_tenk_summary_card(props)
