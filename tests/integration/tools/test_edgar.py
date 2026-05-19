"""Live SEC EDGAR round-trip. Skipped by default.

Run with ``make test-int`` after ensuring ``EDGAR_USER_AGENT`` in your
``.env`` is a real contact ("<Name> <email>"). The test exercises the
two JSON endpoints; ``fetch_filing_document`` is exercised by the unit
respx mocks and intentionally skipped here to avoid the ~5 MB 10-K
download on every integration run.
"""

from __future__ import annotations

import pytest

from mcp_financial_data.settings import reload_settings
from mcp_financial_data.tools.edgar import (
    fetch_company_facts,
    list_filings,
)

pytestmark = pytest.mark.integration

# Apple Inc. -- stable, large 10-K filer.
_AAPL_CIK = "0000320193"


@pytest.mark.asyncio
async def test_live_list_filings_aapl_returns_at_least_one_10k() -> None:
    settings = reload_settings()
    if not settings.edgar_user_agent.strip() or "@" not in settings.edgar_user_agent:
        pytest.skip("EDGAR_USER_AGENT not configured with a real contact")
    filings = await list_filings(_AAPL_CIK, form="10-K", limit=1)
    assert filings, "expected at least one 10-K for AAPL"
    assert filings[0].form == "10-K"
    assert filings[0].cik == _AAPL_CIK


@pytest.mark.asyncio
async def test_live_company_facts_aapl_has_revenues_concept() -> None:
    settings = reload_settings()
    if not settings.edgar_user_agent.strip() or "@" not in settings.edgar_user_agent:
        pytest.skip("EDGAR_USER_AGENT not configured with a real contact")
    facts = await fetch_company_facts(_AAPL_CIK)
    revenues = [f for f in facts if f.concept == "Revenues" and f.unit == "USD"]
    assert revenues, "expected at least one us-gaap:Revenues USD fact for AAPL"
