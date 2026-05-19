"""Tests for ``mcp_financial_data.tools.edgar`` per ADR 0006.

Covers:

- Pydantic shape validation (preserved from the scaffold).
- UA header enforcement (preserved + extended).
- respx-mocked roundtrips for submissions, company-facts, filing-document.
- Retry on 429 / 5xx via tenacity.
- 24-hour cache hit avoids a second HTTP call.
- Rate-limit smoke: 30 concurrent calls take >= 2.9 s.
"""

from __future__ import annotations

import asyncio
import time
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from mcp_financial_data.tools import edgar as edgar_mod
from mcp_financial_data.tools.cache import SqliteCache
from mcp_financial_data.tools.edgar import (
    EdgarConfigError,
    EdgarFact,
    EdgarFiling,
    fetch_company_facts,
    fetch_filing_document,
    list_filings,
)


@pytest.fixture(autouse=True)
def _isolated_edgar_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point every test at a fresh on-disk cache so runs don't see prior state."""
    store = SqliteCache(path=tmp_path / "edgar_test_cache.sqlite")
    monkeypatch.setattr(edgar_mod, "_DEFAULT_CACHE", store, raising=False)


# ---------------------------------------------------------------------------
# Pydantic shape (preserved)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# User-Agent enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_filings_requires_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EDGAR_USER_AGENT", "")
    from mcp_financial_data.settings import reload_settings

    reload_settings()
    with pytest.raises(EdgarConfigError, match="EDGAR_USER_AGENT"):
        await list_filings("0000320193")


@pytest.mark.asyncio
async def test_list_filings_sends_configured_user_agent() -> None:
    body = _submissions_body_aapl()
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get("https://data.sec.gov/submissions/CIK0000320193.json").mock(
            return_value=httpx.Response(200, json=body)
        )
        await list_filings("0000320193", limit=1)
    sent = route.calls.last.request
    ua = sent.headers["user-agent"]
    assert "@" in ua, f"User-Agent must include a contact, got {ua!r}"


# ---------------------------------------------------------------------------
# list_filings
# ---------------------------------------------------------------------------


def _submissions_body_aapl() -> dict[str, object]:
    return {
        "cik": "320193",
        "name": "Apple Inc.",
        "filings": {
            "recent": {
                "accessionNumber": [
                    "0000320193-25-000001",
                    "0000320193-25-000002",
                ],
                "filingDate": ["2025-11-01", "2025-10-30"],
                "form": ["10-K", "8-K"],
                "primaryDocument": ["aapl-10k.htm", "aapl-8k.htm"],
                "primaryDocDescription": ["Annual report", "Current report"],
            }
        },
    }


@pytest.mark.asyncio
async def test_list_filings_parses_recent_submissions() -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://data.sec.gov/submissions/CIK0000320193.json").mock(
            return_value=httpx.Response(200, json=_submissions_body_aapl())
        )
        filings = await list_filings("0000320193", limit=10)
    assert len(filings) == 2
    assert filings[0].form == "10-K"
    assert filings[0].accession_number == "0000320193-25-000001"
    assert filings[0].filing_date == date(2025, 11, 1)
    assert filings[0].primary_document == "aapl-10k.htm"


@pytest.mark.asyncio
async def test_list_filings_filters_by_form() -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://data.sec.gov/submissions/CIK0000320193.json").mock(
            return_value=httpx.Response(200, json=_submissions_body_aapl())
        )
        filings = await list_filings("0000320193", form="10-K", limit=10)
    assert len(filings) == 1
    assert filings[0].form == "10-K"


@pytest.mark.asyncio
async def test_list_filings_honors_limit() -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://data.sec.gov/submissions/CIK0000320193.json").mock(
            return_value=httpx.Response(200, json=_submissions_body_aapl())
        )
        filings = await list_filings("0000320193", limit=1)
    assert len(filings) == 1


# ---------------------------------------------------------------------------
# fetch_company_facts
# ---------------------------------------------------------------------------


def _company_facts_body_msft() -> dict[str, object]:
    return {
        "cik": 789019,
        "entityName": "Microsoft Corp.",
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "label": "Revenues",
                    "description": "Total revenues",
                    "units": {
                        "USD": [
                            {
                                "end": "2025-06-30",
                                "val": 270_000_000_000,
                                "accn": "0000789019-25-000010",
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2025-07-30",
                            }
                        ]
                    },
                }
            }
        },
    }


@pytest.mark.asyncio
async def test_fetch_company_facts_parses_xbrl_units() -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json").mock(
            return_value=httpx.Response(200, json=_company_facts_body_msft())
        )
        facts = await fetch_company_facts("0000789019")
    assert len(facts) == 1
    fact = facts[0]
    assert fact.cik == "0000789019"
    assert fact.concept == "Revenues"
    assert fact.unit == "USD"
    assert fact.value == 270_000_000_000.0
    assert fact.fiscal_year == 2025
    assert fact.fiscal_period == "FY"
    assert fact.end_date == date(2025, 6, 30)
    assert fact.accession_number == "0000789019-25-000010"


# ---------------------------------------------------------------------------
# fetch_filing_document
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_filing_document_returns_bytes() -> None:
    accession = "0000320193-25-000001"
    accn_nodash = accession.replace("-", "")
    cik_num = "320193"  # leading zeros stripped per EDGAR URL convention
    url = f"https://www.sec.gov/Archives/edgar/data/{cik_num}/{accn_nodash}/aapl-10k.htm"
    body = b"<html><body>10-K</body></html>"
    with respx.mock(assert_all_called=True) as mock:
        mock.get(url).mock(return_value=httpx.Response(200, content=body))
        out = await fetch_filing_document("0000320193", accession, "aapl-10k.htm")
    assert out == body


# ---------------------------------------------------------------------------
# Retries (tenacity) and cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_filings_retries_on_429_then_succeeds() -> None:
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get("https://data.sec.gov/submissions/CIK0000320193.json").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "0"}),
                httpx.Response(200, json=_submissions_body_aapl()),
            ]
        )
        filings = await list_filings("0000320193", limit=1)
    assert route.call_count == 2
    assert filings[0].accession_number == "0000320193-25-000001"


@pytest.mark.asyncio
async def test_list_filings_uses_cache_on_second_call() -> None:
    """Two identical calls within TTL should hit the network exactly once."""
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get("https://data.sec.gov/submissions/CIK0000320193.json").mock(
            return_value=httpx.Response(200, json=_submissions_body_aapl())
        )
        first = await list_filings("0000320193", limit=1)
        second = await list_filings("0000320193", limit=1)
    assert route.call_count == 1, "second call must be served from cache"
    assert first[0].accession_number == second[0].accession_number


# ---------------------------------------------------------------------------
# Rate-limit smoke (ADR 0006 acceptance bullet)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_30_concurrent_list_filings_take_at_least_2_9s(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """30 concurrent EDGAR calls must take >= 2.9 s wall-clock at 10 req/sec."""
    # Force a fresh limiter for this test so prior calls in the suite
    # don't leak state into the wall-clock measurement.
    from mcp_financial_data.tools import _ratelimit as rl_mod

    fresh_bucket = rl_mod.TokenBucket(rate_per_sec=rl_mod.EDGAR_MAX_PER_SEC)
    monkeypatch.setattr(rl_mod, "EDGAR_TOKEN_BUCKET", fresh_bucket)
    monkeypatch.setattr(edgar_mod, "EDGAR_TOKEN_BUCKET", fresh_bucket)

    with respx.mock(assert_all_called=False) as mock:
        # Each unique URL gets one route; 30 unique CIKs to force 30 fetches.
        for i in range(30):
            cik = f"{i:010d}"
            body = {
                "cik": str(int(cik)),
                "name": f"Fixture {i}",
                "filings": {
                    "recent": {
                        "accessionNumber": [],
                        "filingDate": [],
                        "form": [],
                        "primaryDocument": [],
                        "primaryDocDescription": [],
                    }
                },
            }
            mock.get(f"https://data.sec.gov/submissions/CIK{cik}.json").mock(
                return_value=httpx.Response(200, json=body)
            )

        t0 = time.perf_counter()
        await asyncio.gather(*(list_filings(f"{i:010d}", limit=1) for i in range(30)))
        elapsed = time.perf_counter() - t0
    assert elapsed >= 2.9, f"30 concurrent EDGAR calls took {elapsed:.3f}s, expected >=2.9s"
