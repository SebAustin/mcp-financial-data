"""SEC EDGAR async client.

Compliance: every request carries the contact User-Agent from
``settings.edgar_user_agent`` and is rate-limited to ≤ 10 req/sec.
The full implementation lives in ``prompts/02_edgar_client.md``.
"""

from __future__ import annotations

from datetime import date
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from mcp_financial_data.settings import Settings, get_settings

EDGAR_BASE_URL: Final[str] = "https://data.sec.gov"
EDGAR_FILES_URL: Final[str] = "https://www.sec.gov/Archives/edgar"


class EdgarConfigError(Exception):
    """User-Agent missing/invalid, or rate-limit config out of range."""


class EdgarFiling(BaseModel):
    """One row from EDGAR submissions API."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cik: str = Field(..., min_length=1, max_length=10)
    accession_number: str = Field(..., pattern=r"^\d{10}-\d{2}-\d{6}$")
    form: str = Field(..., min_length=1, max_length=20)
    filing_date: date
    primary_document: str = Field(..., min_length=1)
    primary_doc_description: str | None = None


class EdgarFact(BaseModel):
    """One XBRL fact returned by the company-facts API."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cik: str
    concept: str = Field(..., description="us-gaap concept, e.g. 'Revenues'.")
    unit: str = Field(..., description="e.g. 'USD', 'shares'.")
    value: float
    fiscal_year: int = Field(..., ge=1990, le=2100)
    fiscal_period: str = Field(..., pattern=r"^(FY|Q[1-4]|H[12])$")
    end_date: date
    accession_number: str


def _require_user_agent(settings: Settings) -> str:
    """Return the configured EDGAR User-Agent or raise.

    Per the EDGAR Fair Access policy, requests without a contact UA can be
    blocked at the SEC's discretion. We treat absence as a hard error.
    """
    ua = settings.edgar_user_agent.strip()
    if not ua or "@" not in ua:
        raise EdgarConfigError(
            "EDGAR_USER_AGENT must be set to '<Name> <contact@example.com>'. "
            "See SEC Fair Access: https://www.sec.gov/os/accessing-edgar-data"
        )
    return ua


async def list_filings(cik: str, *, form: str | None = None, limit: int = 40) -> list[EdgarFiling]:
    """List recent filings for a CIK, newest first.

    Args:
        cik: 10-digit CIK (zero-padded).
        form: Optional filing form filter (e.g. "10-K").
        limit: Max number of filings to return (1..1000).

    See ``prompts/02_edgar_client.md``.
    """
    _ = _require_user_agent(get_settings())
    _ = (cik, form, limit)
    raise NotImplementedError("see prompts/02_edgar_client.md")


async def fetch_company_facts(cik: str) -> list[EdgarFact]:
    """Fetch all XBRL facts for a CIK from the company-facts API.

    See ``prompts/02_edgar_client.md``.
    """
    _ = _require_user_agent(get_settings())
    _ = cik
    raise NotImplementedError("see prompts/02_edgar_client.md")


async def fetch_filing_document(cik: str, accession_number: str, document: str) -> bytes:
    """Fetch the raw bytes of a single document inside a filing.

    See ``prompts/02_edgar_client.md``.
    """
    _ = _require_user_agent(get_settings())
    _ = (cik, accession_number, document)
    raise NotImplementedError("see prompts/02_edgar_client.md")
