# ADR 0006 — EDGAR rate limit + 24h response cache

* Status: Accepted
* Date: 2026-05-18
* Deciders: Sebastien Henry

## Context and Problem Statement

`tools/edgar.py`, `tools/fred.py`, and `tools/polygon.py` together drive
every external data fetch in this server. Three concerns force a shared
design rather than per-client one-offs:

1. **SEC Fair Access (HARD).** The SEC publishes a Fair Access policy for
   the EDGAR APIs. Violation gets the source IP banned. Every request must
   carry a contact `User-Agent` header and the process must stay below
   **10 requests / second** sustained across all concurrent callers.
2. **Spend cap.** `MAX_API_SPEND_USD` is enforced in the extractor and
   harness; the eval harness re-runs the same EDGAR/FRED/Polygon calls on
   every CI run and every nightly run. Without caching, eval runs would
   either (a) burn budget on the metered APIs or (b) hammer EDGAR.
3. **Reproducibility.** The eval harness needs the same upstream answer
   between two runs of the same eval slice on the same SHA — otherwise the
   citation-coverage and exec-accuracy deltas are not interpretable.

## Decision Drivers

* `.cursor/rules/edgar-fair-access.mdc` mandates the UA header, the 10/sec
  cap with `asyncio.Semaphore(10)` plus a token bucket, `tenacity` retries
  on 429 / 5xx, and ≥ 24-hour cache TTL.
* Master `.cursorrules` §8 (Reproducibility) requires pinned dependencies
  and deterministic behavior across runs.
* CI does not have Postgres. The Authentik integration test from
  prompt 01 already established the precedent: CI runs unit + smoke,
  integration tests are skipped by default and rely on operator-supplied
  env vars.
* Adding a Postgres client (`asyncpg`, `psycopg`) is a non-trivial
  dependency decision that deserves its own ADR amendment and should not
  be bundled into prompt 02.

## Considered Options

* **Per-client rate limiting and caching.** Tightest coupling between
  policy and call site. Highest risk of one client violating Fair Access
  because someone forgot the semaphore. Rejected.
* **Shared `_ratelimit.py` module with `Semaphore(10)` + sliding-window
  token bucket, shared `cache.py` with a `CacheStore` Protocol.** One
  place to audit the policy. Both clients depend on the same primitives.
  Selected.
* **Postgres + SQLite cache in one PR.** Doubles the dependency surface
  and the test matrix. Rejected for this PR; deferred to a follow-up.
* **`aiosqlite` as the SQLite driver.** New direct dependency. Tempting
  for stylistic consistency with the rest of the async code. Rejected
  in favor of stdlib `sqlite3` wrapped in `asyncio.to_thread`, which is
  zero-dep and matches the eval-harness's existing pattern (e.g.
  `subprocess` for git SHA).

## Decision Outcome

### Rate limiter

Single shared `tools/_ratelimit.py` module with two primitives:

1. `EDGAR_CONCURRENCY = asyncio.Semaphore(10)` — caps in-flight requests
   at 10. Defends against unbounded concurrency exhausting sockets.
2. `EDGAR_TOKEN_BUCKET = TokenBucket(rate_per_sec=10)` — sliding-window
   token bucket. Tracks request timestamps in a `deque`, evicts entries
   older than `1.0 s` on each `acquire()`, sleeps when the window is full.

`tools/edgar.py` calls `await EDGAR_TOKEN_BUCKET.acquire()` then enters
`async with EDGAR_CONCURRENCY`. FRED and Polygon do not gate through the
EDGAR limiter (they have separate per-key quotas managed by their
operators).

### Cache

Single shared `tools/cache.py` module with:

```python
class CacheStore(Protocol):
    async def get(self, key: str) -> bytes | None: ...
    async def set(self, key: str, value: bytes, *, ttl_seconds: int) -> None: ...
```

- `SqliteCache(path: Path)` implements the protocol via stdlib `sqlite3`
  + `asyncio.to_thread`. Schema is a single `(key TEXT PRIMARY KEY, value
  BLOB NOT NULL, expires_at REAL NOT NULL)` table.
- `get_default_cache(settings)` returns a process-shared `SqliteCache`
  rooted at `evals/.cache.sqlite` (see `.cursor/rules/edgar-fair-access.mdc`).
- Cache key for EDGAR GET requests: the absolute URL. The Accept header is
  not part of the key because EDGAR returns the same body regardless.
- Default TTL: 24 hours (`86_400` seconds), matching the rule.
- Cache miss raises nothing; clients fall through to the HTTP path.

### Postgres (deferred)

A `PostgresCache` implementation of `CacheStore` is planned but **not**
shipped in this PR. The Protocol is the seam: a future PR adds the
`asyncpg`-backed class and a `get_default_cache` decision based on
`settings.postgres_dsn`. Until then, every environment uses SQLite.

### Retries

`tenacity.retry` with exponential backoff (multiplier=0.5, min=0.5,
max=4.0), `stop_after_attempt(3)`, and `retry_if_exception_type` on the
HTTPX transport errors plus a custom `_RetryableHTTPStatus` raised on
429 / 5xx. Total wall-clock budget ≤ 8 s.

## Consequences

* Every EDGAR request carries a contact UA, is rate-limited, retried on
  429 / 5xx, and goes through the SQLite cache. A new EDGAR endpoint
  cannot bypass the limiter without re-touching `_ratelimit.py`.
* The eval harness benefits from the same cache: a `--full` run on the
  same SHA the next day still does the network round-trip, but a re-run
  inside the same 24h window is free.
* CI never writes a cache file because `make ci` runs `--smoke --offline`
  and never touches the EDGAR/FRED/Polygon code paths. `evals/.cache.sqlite`
  is gitignored.
* The Postgres path is documented but unimplemented. Anyone needing it
  before the follow-up PR can subclass `CacheStore` and inject.

## References

* https://www.sec.gov/os/accessing-edgar-data — SEC Fair Access policy.
* `.cursor/rules/edgar-fair-access.mdc` — project-local enforcement.
* `https://fred.stlouisfed.org/docs/api/fred/` — FRED API.
* `https://polygon.io/docs/rest` — Polygon REST API.
* ADR 0002 — MCP spec target and transport.
* ADR 0004 — OAuth 2.1 RS (companion auth layer).
