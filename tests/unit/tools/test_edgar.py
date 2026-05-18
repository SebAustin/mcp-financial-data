"""Tests for ``mcp_financial_data.tools.edgar`` stubs + UA enforcement."""

from __future__ import annotations

from datetime import date

import pytest

from mcp_financial_data.tools.edgar import (
    EdgarConfigError,
    EdgarFact,
    EdgarFiling,
    fetch_company_facts,
    fetch_filing_document,
    list_filings,
)


def test_filing_model_rejects_bad_accession() -> None:
    with pytest.raises(ValueError):
        EdgarFiling.model_validate(
            {
                "cik": "0000320193",
                "accession_number": "not-an-accession",
                "form": "10-K",
                "filing_date": "2025-11-01",
                "primary_document": "aapl-10k.htm",
            }
        )


def test_filing_model_happy_path() -> None:
    f = EdgarFiling(
        cik="0000320193",
        accession_number="0000320193-25-000001",
        form="10-K",
        filing_date=date(2025, 11, 1),
        primary_document="aapl-10k.htm",
    )
    assert f.form == "10-K"


def test_fact_model_period_pattern() -> None:
    EdgarFact(
        cik="0000320193",
        concept="Revenues",
        unit="USD",
        value=400.0e9,
        fiscal_year=2025,
        fiscal_period="FY",
        end_date=date(2025, 9, 28),
        accession_number="0000320193-25-000001",
    )
    with pytest.raises(ValueError):
        EdgarFact.model_validate(
            {
                "cik": "0000320193",
                "concept": "Revenues",
                "unit": "USD",
                "value": 1.0,
                "fiscal_year": 2025,
                "fiscal_period": "ZZ",
                "end_date": "2025-09-28",
                "accession_number": "0000320193-25-000001",
            }
        )


@pytest.mark.asyncio
async def test_list_filings_requires_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EDGAR_USER_AGENT", "")
    from mcp_financial_data.settings import reload_settings

    reload_settings()
    with pytest.raises(EdgarConfigError, match="EDGAR_USER_AGENT"):
        await list_filings("0000320193")


@pytest.mark.asyncio
async def test_list_filings_is_stub() -> None:
    with pytest.raises(NotImplementedError, match=r"prompts/02_edgar_client\.md"):
        await list_filings("0000320193")


@pytest.mark.asyncio
async def test_company_facts_is_stub() -> None:
    with pytest.raises(NotImplementedError, match=r"prompts/02_edgar_client\.md"):
        await fetch_company_facts("0000320193")


@pytest.mark.asyncio
async def test_fetch_filing_document_is_stub() -> None:
    with pytest.raises(NotImplementedError, match=r"prompts/02_edgar_client\.md"):
        await fetch_filing_document("0000320193", "0000320193-25-000001", "aapl-10k.htm")
