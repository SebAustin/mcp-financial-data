"""Tests for ``mcp_financial_data.extractors.tenk`` stubs + spend cap path."""

from __future__ import annotations

import pytest

from mcp_financial_data.extractors.tenk import (
    Citation,
    CitedClaim,
    ExtractionResult,
    ExtractorSpendCapError,
    TenKSection,
    extract_tenk_section,
)


def test_citation_requires_minimum_fields() -> None:
    Citation(
        document_title="AAPL 10-K Item 1A",
        start_char_index=0,
        end_char_index=10,
        cited_text="Apple is",
    )
    with pytest.raises(ValueError):
        Citation.model_validate(
            {
                "document_title": "AAPL 10-K Item 1A",
                "start_char_index": -1,
                "end_char_index": 10,
                "cited_text": "x",
            }
        )


def test_cited_claim_requires_at_least_one_citation() -> None:
    with pytest.raises(ValueError):
        CitedClaim.model_validate({"text": "fact", "citations": []})


def test_extraction_result_default_empty() -> None:
    er = ExtractionResult(
        section="item_1a_risk_factors",
        document_title="AAPL 10-K Item 1A",
        model="claude-sonnet-4-5-20260301",
    )
    assert er.facts == ()
    assert er.notes == ()
    assert er.cost_usd == 0.0


@pytest.mark.asyncio
async def test_extract_tenk_section_is_stub() -> None:
    section = TenKSection(
        section="item_1a_risk_factors",
        document_title="AAPL 10-K Item 1A",
        text="Apple operates in highly competitive markets...",
    )
    with pytest.raises(NotImplementedError, match=r"prompts/03_tenk_citations_extractor\.md"):
        await extract_tenk_section(section)


@pytest.mark.asyncio
async def test_extract_tenk_section_enforces_spend_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_API_SPEND_USD", "0")
    from mcp_financial_data.settings import reload_settings

    reload_settings()
    section = TenKSection(
        section="item_1_business",
        document_title="AAPL 10-K Item 1",
        text="Apple Inc. designs, manufactures, and markets...",
    )
    with pytest.raises(ExtractorSpendCapError, match="MAX_API_SPEND_USD"):
        await extract_tenk_section(section)
