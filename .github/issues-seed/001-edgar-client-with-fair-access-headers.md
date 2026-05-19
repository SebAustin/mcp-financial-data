---
title: "feat: implement EDGAR async client with Fair Access headers + 10/sec rate limit"
labels: [enhancement, w1]
assignees: [SebAustin]
---

## Problem

The scaffold ships typed stubs for `tools/edgar.py`. Production-grade
implementations are required for the SEC EDGAR submissions, company-facts,
and filing-document endpoints, with full Fair Access compliance:

- Mandatory contact `User-Agent` header sourced from `EDGAR_USER_AGENT`
  env var.
- Process-wide rate limit ≤ 10 req/sec via shared `asyncio.Semaphore`
  + token bucket.
- `tenacity` retries on 429 / 5xx (max 3, total wait ≤ 8 s).
- 24-hour Postgres response cache (SQLite fallback).

Hard rules:
`.cursor/rules/edgar-fair-access.mdc`. Decision: ADR 0006 (new — to be
added in this PR).

## Acceptance criteria

- [ ] `list_filings`, `fetch_company_facts`, `fetch_filing_document`
  return typed pydantic models, no `dict[str, Any]` leaks.
- [ ] UA header is set on every request; missing UA raises
  `EdgarConfigError` before any HTTP call.
- [ ] Rate-limit smoke test: 30 concurrent calls take ≥ 2.9 s.
- [ ] `tests/unit/tools/test_edgar.py` extended with `respx` mocks for
  all 3 endpoints.
- [ ] Eval cases `edgar-aapl-list-10k-2025`, `edgar-msft-revenues-fy2025`,
  `edgar-googl-list-8k-2025` pass against mocked responses.
- [ ] Nightly eval workflow stays green for 3 consecutive days.

## References

- https://www.sec.gov/os/accessing-edgar-data
- ADR 0002 (`docs/adr/0002-mcp-spec-2025-11-25.md`)
- `.cursor/rules/edgar-fair-access.mdc`
