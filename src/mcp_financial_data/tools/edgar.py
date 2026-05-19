"""SEC EDGAR async client.

Compliance: every request carries the contact User-Agent from
``settings.edgar_user_agent`` and is rate-limited to <= 10 req/sec
through the process-shared limiter in :mod:`tools._ratelimit`. GET
responses are cached for 24 h via :mod:`tools.cache` per ADR 0006.

Endpoints used (any other endpoint requires an ADR before use):

- ``https://data.sec.gov/submissions/CIK{cik}.json``
- ``https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json``
- ``https://www.sec.gov/Archives/edgar/data/{cik_num}/{accn_nodash}/{file}``
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Final

import httpx
from pydantic import BaseModel, ConfigDict, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from mcp_financial_data.logging import get_logger
from mcp_financial_data.settings import Settings, get_settings
from mcp_financial_data.tools._ratelimit import EDGAR_CONCURRENCY, EDGAR_TOKEN_BUCKET
from mcp_financial_data.tools.cache import CacheStore, get_default_cache

EDGAR_BASE_URL: Final[str] = "https://data.sec.gov"
EDGAR_FILES_URL: Final[str] = "https://www.sec.gov/Archives/edgar"

#: HTTP timeout for any single EDGAR request. SEC's edge is reliably fast.
_HTTP_TIMEOUT_SECONDS: Final[float] = 15.0

#: Cache TTL for GET responses. Matches ADR 0006 and the Fair Access rule.
_CACHE_TTL_SECONDS: Final[int] = 24 * 60 * 60

_log = get_logger("tools.edgar")


class EdgarConfigError(Exception):
    """User-Agent missing/invalid, or rate-limit config out of range."""


class EdgarHTTPError(Exception):
    """Non-retryable HTTP failure from an EDGAR endpoint."""


class _RetryableHTTPStatus(Exception):
    """Internal signal that an EDGAR response should trigger a tenacity retry."""


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


# Module-level cache + lazily-built client. Tests override _DEFAULT_CACHE
# via monkeypatch to point at a tmp_path-rooted SqliteCache.
_DEFAULT_CACHE: CacheStore = get_default_cache(get_settings())


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


@retry(
    reraise=True,
    retry=retry_if_exception_type((httpx.HTTPError, _RetryableHTTPStatus)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
)
async def _http_get(url: str, *, ua: str) -> bytes:
    """Single GET through the EDGAR rate limiter, retry on 429/5xx.

    Returns raw response bytes. Caller is responsible for json decoding.
    """
    await EDGAR_TOKEN_BUCKET.acquire()
    async with EDGAR_CONCURRENCY:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.get(url, headers={"User-Agent": ua, "Accept": "application/json"})
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            _log.warning(
                "edgar.http.retryable",
                url=url,
                status=resp.status_code,
            )
            raise _RetryableHTTPStatus(f"status={resp.status_code} url={url}")
        if resp.status_code >= 400:
            raise EdgarHTTPError(f"EDGAR GET {url} failed: {resp.status_code}")
        return resp.content


async def _get_cached(url: str, *, ua: str) -> bytes:
    """Cache-aware GET. Returns response bytes from cache or live network."""
    cached = await _DEFAULT_CACHE.get(url)
    if cached is not None:
        _log.info("edgar.cache.hit", url=url)
        return cached
    body = await _http_get(url, ua=ua)
    await _DEFAULT_CACHE.set(url, body, ttl_seconds=_CACHE_TTL_SECONDS)
    return body


def _pad_cik(cik: str) -> str:
    """Return the 10-digit zero-padded CIK accepted by data.sec.gov."""
    stripped = cik.strip()
    if not stripped.isdigit() or len(stripped) > 10:
        raise EdgarConfigError(f"invalid CIK {cik!r}; must be up to 10 digits")
    return stripped.zfill(10)


async def list_filings(cik: str, *, form: str | None = None, limit: int = 40) -> list[EdgarFiling]:
    """List recent filings for a CIK, newest first.

    Args:
        cik: 10-digit CIK (zero-padded or any digit-length up to 10).
        form: Optional filing form filter (e.g. ``"10-K"``).
        limit: Max number of filings to return (1..1000).
    """
    settings = get_settings()
    ua = _require_user_agent(settings)
    padded = _pad_cik(cik)
    url = f"{EDGAR_BASE_URL}/submissions/CIK{padded}.json"

    body = await _get_cached(url, ua=ua)
    data = json.loads(body)
    recent = data.get("filings", {}).get("recent", {})
    rows = _zip_submissions_table(padded, recent)
    if form is not None:
        rows = [r for r in rows if r.form == form]
    return rows[:limit]


def _zip_submissions_table(cik: str, recent: dict[str, Any]) -> list[EdgarFiling]:
    """Convert the EDGAR submissions parallel-arrays into typed rows."""
    accessions = recent.get("accessionNumber", []) or []
    dates = recent.get("filingDate", []) or []
    forms = recent.get("form", []) or []
    primary_docs = recent.get("primaryDocument", []) or []
    descs = recent.get("primaryDocDescription", []) or []
    n = min(len(accessions), len(dates), len(forms), len(primary_docs))
    out: list[EdgarFiling] = []
    for i in range(n):
        desc = descs[i] if i < len(descs) else None
        out.append(
            EdgarFiling(
                cik=cik,
                accession_number=accessions[i],
                form=forms[i],
                filing_date=date.fromisoformat(dates[i]),
                primary_document=primary_docs[i],
                primary_doc_description=desc or None,
            )
        )
    return out


async def fetch_company_facts(cik: str) -> list[EdgarFact]:
    """Fetch all XBRL facts for a CIK from the company-facts API."""
    settings = get_settings()
    ua = _require_user_agent(settings)
    padded = _pad_cik(cik)
    url = f"{EDGAR_BASE_URL}/api/xbrl/companyfacts/CIK{padded}.json"
    body = await _get_cached(url, ua=ua)
    data = json.loads(body)
    return _flatten_company_facts(padded, data)


def _flatten_company_facts(cik: str, data: dict[str, Any]) -> list[EdgarFact]:
    """Walk the nested ``facts[taxonomy][concept][units][unit][...]`` shape."""
    out: list[EdgarFact] = []
    facts = data.get("facts", {})
    if not isinstance(facts, dict):
        return out
    for _taxonomy, concepts in facts.items():
        if not isinstance(concepts, dict):
            continue
        for concept, concept_data in concepts.items():
            if not isinstance(concept_data, dict):
                continue
            units = concept_data.get("units", {})
            if not isinstance(units, dict):
                continue
            for unit, observations in units.items():
                if not isinstance(observations, list):
                    continue
                for obs in observations:
                    if not isinstance(obs, dict):
                        continue
                    try:
                        out.append(
                            EdgarFact(
                                cik=cik,
                                concept=concept,
                                unit=unit,
                                value=float(obs["val"]),
                                fiscal_year=int(obs["fy"]),
                                fiscal_period=str(obs["fp"]),
                                end_date=date.fromisoformat(obs["end"]),
                                accession_number=str(obs["accn"]),
                            )
                        )
                    except (KeyError, TypeError, ValueError):
                        # Skip malformed rows; upstream EDGAR data is permissive.
                        continue
    return out


async def fetch_filing_document(cik: str, accession_number: str, document: str) -> bytes:
    """Fetch the raw bytes of a single document inside a filing."""
    settings = get_settings()
    ua = _require_user_agent(settings)
    cik_num = str(int(_pad_cik(cik)))  # EDGAR Archives URLs strip leading zeros
    accn_nodash = accession_number.replace("-", "")
    url = f"{EDGAR_FILES_URL}/data/{cik_num}/{accn_nodash}/{document}"
    return await _get_cached(url, ua=ua)
