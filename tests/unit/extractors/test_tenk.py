"""Tests for ``mcp_financial_data.extractors.tenk``.

Covers the Citations API integration end-to-end via ``respx``-mocked
Anthropic responses. The four scenarios mandated by prompt 03 are:

1. happy-path mock returning two cited claims.
2. mock returning one cited and one uncited block; uncited goes to ``notes``
   and is NOT in ``facts``.
3. mock returning a citation whose ``cited_text`` does not appear in the
   source document; that fact is dropped.
4. spend-cap test still passes (the cap=0 path raises before any HTTP call).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from mcp_financial_data.extractors.tenk import (
    Citation,
    CitedClaim,
    ExtractionResult,
    ExtractorSpendCapError,
    TenKSection,
    extract_tenk_section,
    get_total_spend_usd,
    reset_spend_counter,
)

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"


@pytest.fixture(autouse=True)
def _reset_spend() -> None:
    """Reset the process-local spend counter between tests."""
    reset_spend_counter()


def _make_citation(
    *,
    cited_text: str,
    start: int,
    end: int,
    document_title: str = "AAPL 10-K Item 1A",
    document_index: int = 0,
) -> dict[str, Any]:
    return {
        "type": "char_location",
        "cited_text": cited_text,
        "document_title": document_title,
        "document_index": document_index,
        "start_char_index": start,
        "end_char_index": end,
    }


def _make_message_payload(
    *,
    content: list[dict[str, Any]],
    model: str = "claude-sonnet-4-6-20260301",
    input_tokens: int = 250,
    output_tokens: int = 60,
) -> dict[str, Any]:
    return {
        "id": "msg_test_0001",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
    }


SOURCE_TEXT = (
    "The Company's business depends on the timely receipt and successful "
    "integration of components and finished products from third-party "
    "manufacturers. The Company is exposed to global macroeconomic "
    "conditions, including inflation, interest rates, and foreign "
    "exchange fluctuations."
)


def _section() -> TenKSection:
    return TenKSection(
        section="item_1a_risk_factors",
        document_title="AAPL 10-K Item 1A",
        text=SOURCE_TEXT,
    )


# ---------------------------------------------------------------------------
# Pydantic schema sanity tests (kept from the day-0 stub).
# ---------------------------------------------------------------------------


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
        model="claude-sonnet-4-6-20260301",
    )
    assert er.facts == ()
    assert er.notes == ()
    assert er.cost_usd == 0.0


# ---------------------------------------------------------------------------
# Citations API integration (respx-mocked).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock(assert_all_called=True)
async def test_happy_path_two_cited_claims(respx_mock: respx.Router) -> None:
    """Mock returns two cited blocks → two ``CitedClaim`` facts, no notes."""
    payload = _make_message_payload(
        content=[
            {
                "type": "text",
                "text": (
                    "Apple depends on the timely receipt and successful "
                    "integration of components from third parties."
                ),
                "citations": [
                    _make_citation(
                        cited_text=(
                            "The Company's business depends on the timely "
                            "receipt and successful integration of components"
                        ),
                        start=0,
                        end=92,
                    )
                ],
            },
            {
                "type": "text",
                "text": (
                    "Apple is exposed to global macroeconomic conditions including inflation."
                ),
                "citations": [
                    _make_citation(
                        cited_text=(
                            "exposed to global macroeconomic conditions, including inflation"
                        ),
                        start=160,
                        end=220,
                    )
                ],
            },
        ]
    )
    respx_mock.post(ANTHROPIC_MESSAGES_URL).mock(return_value=httpx.Response(200, json=payload))

    result = await extract_tenk_section(_section())

    assert isinstance(result, ExtractionResult)
    assert result.notes == ()
    assert len(result.facts) == 2
    for claim in result.facts:
        assert isinstance(claim, CitedClaim)
        assert len(claim.citations) >= 1
        for citation in claim.citations:
            assert citation.cited_text in SOURCE_TEXT
    assert result.input_tokens == 250
    assert result.output_tokens == 60
    # 250/1M * $3 + 60/1M * $15 = 0.00075 + 0.0009 = 0.00165
    assert result.cost_usd == pytest.approx(0.00165, rel=1e-6)
    assert get_total_spend_usd() == pytest.approx(0.00165, rel=1e-6)


@pytest.mark.asyncio
@respx.mock(assert_all_called=True)
async def test_uncited_block_demoted_to_notes(respx_mock: respx.Router) -> None:
    """Mock returns one cited + one uncited block; uncited → notes only."""
    payload = _make_message_payload(
        content=[
            {
                "type": "text",
                "text": "Apple depends on third-party manufacturers.",
                "citations": [
                    _make_citation(
                        cited_text=(
                            "depends on the timely receipt and successful "
                            "integration of components and finished products "
                            "from third-party manufacturers"
                        ),
                        start=24,
                        end=170,
                    )
                ],
            },
            {
                "type": "text",
                "text": "We believe Apple will weather any storm.",
                "citations": None,
            },
        ]
    )
    respx_mock.post(ANTHROPIC_MESSAGES_URL).mock(return_value=httpx.Response(200, json=payload))

    result = await extract_tenk_section(_section())

    assert len(result.facts) == 1
    assert all("believe" not in claim.text.lower() for claim in result.facts)
    assert len(result.notes) == 1
    note = result.notes[0]
    assert note.startswith("[INFERENCE]")
    assert "weather any storm" in note


@pytest.mark.asyncio
@respx.mock(assert_all_called=True)
async def test_citation_not_in_source_is_dropped(respx_mock: respx.Router) -> None:
    """Citations whose ``cited_text`` is absent from the source → fact dropped."""
    payload = _make_message_payload(
        content=[
            {
                "type": "text",
                "text": "Apple's CEO is Tim Cook.",
                "citations": [
                    _make_citation(
                        cited_text="The Company's CEO, Tim Cook, said in 2026",
                        start=0,
                        end=42,
                    )
                ],
            },
            {
                "type": "text",
                "text": "Apple is exposed to macroeconomic conditions.",
                "citations": [
                    _make_citation(
                        cited_text=(
                            "exposed to global macroeconomic conditions, including inflation"
                        ),
                        start=160,
                        end=220,
                    )
                ],
            },
        ]
    )
    respx_mock.post(ANTHROPIC_MESSAGES_URL).mock(return_value=httpx.Response(200, json=payload))

    result = await extract_tenk_section(_section())

    assert len(result.facts) == 1
    assert "Tim Cook" not in result.facts[0].text
    assert result.notes == ()


@pytest.mark.asyncio
@respx.mock(assert_all_called=True)
async def test_consecutive_same_citation_blocks_merge(respx_mock: respx.Router) -> None:
    """Two consecutive text blocks sharing one citation → one merged claim."""
    citation = _make_citation(
        cited_text=(
            "The Company's business depends on the timely receipt and "
            "successful integration of components"
        ),
        start=0,
        end=92,
    )
    payload = _make_message_payload(
        content=[
            {
                "type": "text",
                "text": "Apple's business depends on timely component receipt ",
                "citations": [citation],
            },
            {
                "type": "text",
                "text": "and successful third-party integration.",
                "citations": [citation],
            },
        ]
    )
    respx_mock.post(ANTHROPIC_MESSAGES_URL).mock(return_value=httpx.Response(200, json=payload))

    result = await extract_tenk_section(_section())

    assert len(result.facts) == 1
    merged = result.facts[0]
    assert "Apple's business" in merged.text
    assert "successful third-party integration" in merged.text
    assert len(merged.citations) == 1


@pytest.mark.asyncio
async def test_extract_tenk_section_enforces_spend_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cap=0 raises before any HTTP call (no respx mock needed)."""
    monkeypatch.setenv("MAX_API_SPEND_USD", "0")
    from mcp_financial_data.settings import reload_settings

    reload_settings()
    with pytest.raises(ExtractorSpendCapError, match="MAX_API_SPEND_USD"):
        await extract_tenk_section(_section())


@pytest.mark.asyncio
@respx.mock(assert_all_called=False)
async def test_extract_tenk_section_cap_already_exhausted(
    monkeypatch: pytest.MonkeyPatch,
    respx_mock: respx.Router,
) -> None:
    """Spend already at cap → refuse before HTTP. Counter check, not env."""
    monkeypatch.setenv("MAX_API_SPEND_USD", "0.0001")
    from mcp_financial_data.settings import reload_settings

    reload_settings()
    route = respx_mock.post(ANTHROPIC_MESSAGES_URL).mock(
        return_value=httpx.Response(200, json=_make_message_payload(content=[]))
    )
    from mcp_financial_data.extractors.tenk import _add_spend

    _add_spend(1.00)  # Saturate the counter past the tiny cap.

    with pytest.raises(ExtractorSpendCapError, match="exhausted"):
        await extract_tenk_section(_section())
    assert route.call_count == 0
