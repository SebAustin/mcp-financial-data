"""Tests for ``mcp_financial_data.apps.ui``."""

from __future__ import annotations

from mcp_financial_data.apps.ui import (
    TENK_SUMMARY_CARD_ID,
    TENK_SUMMARY_CARD_RESOURCE_URI,
    McpUiEnvelope,
    TenKSummaryCardProps,
    _bundle_path,
    bundle_sha256,
    render_tenk_summary_card,
    sec_edgar_browse_url,
)
from mcp_financial_data.evals.fixtures import get_offline_fixture
from mcp_financial_data.extractors.tenk import Citation, CitedClaim, ExtractionResult


def _aapl_risk_extraction() -> ExtractionResult:
    raw = get_offline_fixture("tenk-aapl-risk-factors")
    return ExtractionResult.model_validate(raw)


def test_card_id_is_stable() -> None:
    assert TENK_SUMMARY_CARD_ID == "tenk-summary-card"


def test_props_model_rejects_extras() -> None:
    er = ExtractionResult(
        section="item_1_business",
        document_title="AAPL 10-K Item 1",
        model="claude-sonnet-4-6-20260301",
    )
    try:
        TenKSummaryCardProps.model_validate(
            {
                "extraction": er.model_dump(),
                "cik": "0000320193",
                "company_name": "Apple Inc.",
                "extra": "bad",
            }
        )
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_sec_edgar_browse_url_uses_cgi_bin_pattern() -> None:
    url = sec_edgar_browse_url("0000320193")
    assert url.startswith("https://www.sec.gov/cgi-bin/browse-edgar")
    assert "CIK=320193" in url
    assert "type=10-K" in url


def test_bundle_hash_matches_disk() -> None:
    path = _bundle_path()
    assert path.is_file()
    assert bundle_sha256(path) == bundle_sha256(path)


def test_render_tenk_summary_card_aapl_risk_factors() -> None:
    extraction = _aapl_risk_extraction()
    props = TenKSummaryCardProps(
        extraction=extraction,
        cik="0000320193",
        company_name="Apple Inc.",
    )
    envelope_dict = render_tenk_summary_card(props)
    envelope = McpUiEnvelope.model_validate(envelope_dict)

    assert envelope.id == TENK_SUMMARY_CARD_ID
    assert envelope.component == TENK_SUMMARY_CARD_ID
    assert envelope.resourceUri == TENK_SUMMARY_CARD_RESOURCE_URI
    assert envelope.bundle.sha256 == bundle_sha256()
    assert envelope.bundle.path.endswith("tenk-summary-card.bundle.js")

    assert len(envelope.citationPills) >= 2
    for pill in envelope.citationPills:
        assert pill.url.startswith("https://www.sec.gov/cgi-bin/browse-edgar")
        assert "CIK=" in pill.url

    assert envelope.props["cik"] == "0000320193"
    assert envelope.props["company_name"] == "Apple Inc."
    assert envelope.props["extraction"]["latency_ms"] == 0.0


def test_render_envelope_facts_match_extraction() -> None:
    extraction = ExtractionResult(
        section="item_1a_risk_factors",
        document_title="AAPL 10-K FY2025 Item 1A",
        model="claude-sonnet-4-6-20260301",
        facts=(
            CitedClaim(
                text="One cited fact.",
                citations=(
                    Citation(
                        document_title="AAPL 10-K FY2025 Item 1A",
                        start_char_index=0,
                        end_char_index=4,
                        cited_text="One ",
                    ),
                ),
            ),
        ),
    )
    props = TenKSummaryCardProps(
        extraction=extraction,
        cik="0000320193",
        company_name="Apple Inc.",
    )
    envelope = McpUiEnvelope.model_validate(render_tenk_summary_card(props))
    assert len(envelope.citationPills) == 1
    assert envelope.citationPills[0].claim_text == "One cited fact."
