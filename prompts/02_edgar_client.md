# Prompt 02 — EDGAR / FRED / Polygon async clients

> Owns: `src/mcp_financial_data/tools/{edgar,fred,polygon}.py` and matching
> tests.

You are implementing three async clients. The hard rules are in
`.cursor/rules/edgar-fair-access.mdc`. Read that first. Re-read ADR 0002.

## Goals (in order)

### 1. `tools/edgar.py` (Fair Access)

- `list_filings(cik, *, form=None, limit=40)` → list of `EdgarFiling`.
  Endpoint: `https://data.sec.gov/submissions/CIK{cik}.json`.
- `fetch_company_facts(cik)` → list of `EdgarFact`. Endpoint:
  `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`.
- `fetch_filing_document(cik, accession, document)` → bytes. Endpoint:
  `https://www.sec.gov/Archives/edgar/data/{cik}/{accn_nodash}/{document}`.
- All requests through a single `httpx.AsyncClient` with the contact
  User-Agent from `settings.edgar_user_agent`.
- Rate limit: process-shared `asyncio.Semaphore(10)` plus a token bucket
  to keep ≤ 10 req/sec sustained.
- Retries: `tenacity` exponential, 3 max, total wait ≤ 8 s, on 429 / 5xx.
- Cache: GET responses keyed by URL into Postgres for 24 h (or SQLite
  fallback at `evals/.cache.sqlite` when `POSTGRES_DSN` is unreachable).

### 2. `tools/fred.py`

- `fetch_series(series_id, *, start=None, end=None)` → `FredSeries`.
- Endpoint: `https://api.stlouisfed.org/fred/series/observations`.
- Auth: `&api_key={settings.fred_api_key}`.
- `value` is `None` when FRED returns the literal `"."` placeholder.

### 3. `tools/polygon.py`

- `fetch_aggregates(ticker, *, multiplier, timespan, start, end, adjusted=True, limit=5000)`
  → list of `PolygonAggregateBar`.
- Endpoint: `https://api.polygon.io/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{start}/{end}`.
- Header: `Authorization: Bearer {settings.polygon_api_key}`.

## Acceptance

- `tests/unit/tools/test_edgar.py` extended with `respx` mocks for all
  three EDGAR endpoints; the existing UA-required test still passes.
- `tests/unit/tools/test_fred.py` and `tests/unit/tools/test_polygon.py`
  extended with `respx` mocks.
- A rate-limit smoke test asserts that 30 concurrent EDGAR calls take
  ≥ 2.9 s wall-clock (300 ms / 10 reqs).
- Eval cases `edgar-aapl-list-10k-2025`, `edgar-msft-revenues-fy2025`,
  `edgar-googl-list-8k-2025`, `fred-gdp-q1-2025` flip from offline-fixture
  to mocked-real in `--offline` mode without changing their expected.
- `EVAL_OFFLINE=0 uv run python -m mcp_financial_data.evals.harness --full`
  passes with the `--full` flag against the real APIs (run locally with
  your secrets).

## Files touched

- `src/mcp_financial_data/tools/edgar.py`, `fred.py`, `polygon.py`.
- `src/mcp_financial_data/tools/cache.py` (new — async Postgres / SQLite
  KV adapter).
- `tests/unit/tools/*.py` (extend).
- `tests/integration/tools/*.py` (new; skipped by default).
- `docs/adr/0006-edgar-rate-limit-and-cache.md` (new ADR).
