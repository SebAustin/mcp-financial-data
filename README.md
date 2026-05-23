# mcp-financial-data

> An MCP server (spec **2025-11-25**) for **SEC EDGAR + FRED + Polygon.io** with
> **OAuth 2.1**, a **citation-grounded 10-K extractor** powered by Claude
> Sonnet 4.5, and an **MCP Apps inline UI** for the extracted summary.
>
> Anchor audience: Anthropic Forward Deployed Engineering, Bridgewater /
> Citadel / Anthropic Finance teams.

[![CI](https://github.com/SebAustin/mcp-financial-data/actions/workflows/ci.yml/badge.svg)](https://github.com/SebAustin/mcp-financial-data/actions/workflows/ci.yml)
[![Eval (nightly)](https://github.com/SebAustin/mcp-financial-data/actions/workflows/eval-nightly.yml/badge.svg)](https://github.com/SebAustin/mcp-financial-data/actions/workflows/eval-nightly.yml)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/tag/SebAustin/mcp-financial-data?label=v0.1.0)](https://github.com/SebAustin/mcp-financial-data/releases/tag/v0.1.0)

> **About:** MCP server for SEC EDGAR + FRED + Polygon with OAuth 2.1, a
> citation-grounded 10-K extractor, and MCP Apps inline UI — built for
> Anthropic FDE, Bridgewater / Citadel quant, and Cursor FDE reviewers.

## Demo

Start with the [interactive deck](docs/presentation.html) for the full walkthrough, or scroll the
static slide exports below.

| Step | Command |
| --- | --- |
| Present | [`docs/presentation.html`](docs/presentation.html) — 14-slide interactive project deck (open in any browser; `←` `→` to navigate, `O` for overview). PowerPoint version: [`docs/mcp-financial-data-presentation.pptx`](docs/mcp-financial-data-presentation.pptx) |
| Live MCP | [`docs/demo/cursor-mcp-setup.md`](docs/demo/cursor-mcp-setup.md) — optional Cursor appendix |
| Regenerate slides | `make presentation-export` — re-export PNGs from the HTML deck |

**Story:** analyst asks for AAPL Item 1A risks → cited TenKSummaryCard → eval proof at 1.0 → stack + CI.

![Slide 1 — Cover](docs/presentation/slides/slide-01-cover.png)

<details>
<summary><strong>All 14 presentation slides</strong> (static PNG exports from <code>docs/presentation.html</code>)</summary>

**2 — The problem**

![Slide 2 — The problem](docs/presentation/slides/slide-02-the-problem.png)

**3 — What it is**

![Slide 3 — What it is](docs/presentation/slides/slide-03-what-it-is.png)

**4 — Architecture**

![Slide 4 — Architecture](docs/presentation/slides/slide-04-architecture.png)

**5 — The citation contract**

![Slide 5 — The citation contract](docs/presentation/slides/slide-05-citation-contract.png)

**6 — The output card**

![Slide 6 — The output card](docs/presentation/slides/slide-06-output-card.png)

**7 — OAuth 2.1 security**

![Slide 7 — OAuth 2.1 security](docs/presentation/slides/slide-07-oauth-security.png)

**8 — Data discipline**

![Slide 8 — Data discipline](docs/presentation/slides/slide-08-data-discipline.png)

**9 — Eval harness**

![Slide 9 — Eval harness](docs/presentation/slides/slide-09-eval-harness.png)

**10 — Engineering rigor**

![Slide 10 — Engineering rigor](docs/presentation/slides/slide-10-engineering-rigor.png)

**11 — The stack**

![Slide 11 — The stack](docs/presentation/slides/slide-11-stack.png)

**12 — Story demo**

![Slide 12 — Story demo](docs/presentation/slides/slide-12-story-demo.png)

**13 — Results (v0.1.0)**

![Slide 13 — Results](docs/presentation/slides/slide-13-results.png)

**14 — Recap & close**

![Slide 14 — Recap & close](docs/presentation/slides/slide-14-recap.png)

</details>

## Why this exists

Financial-services AI work consistently fails the same audit checklist:

1. The agent answered with a number, but the citation pointed at the wrong
   filing.
2. The agent dropped a fact silently when the source didn't support it.
3. The MCP integration didn't validate JWT scopes per request.
4. The eval harness wasn't deterministic, so the regression yesterday is
   indistinguishable from a flaky judge today.

Every one of these is a hard constraint in this repo, enforced in CI.

## Architecture

Every request crosses the OAuth 2.1 boundary before anything runs; every external
fetch is rate-limited and cached; every `tenk.*` claim is citation-grounded before it
leaves the server. Thick arrows are the live request path, dotted arrows are control
or replay paths.

```mermaid
flowchart LR
    C["MCP Client<br/>Claude Desktop · Cursor · Goose"]
    OAuth["OAuth 2.1 Resource Server<br/>JWT validation · alg allowlist · PKCE"]

    subgraph core["FastMCP Server — MCP spec 2025-11-25"]
        Router["Tool router +<br/>MCP Apps registry"]
        EDGAR["edgar.list_filings<br/>edgar.company_facts"]
        FRED["fred.series"]
        Polygon["polygon.aggregates"]
        Extractor["tenk.extract_section<br/>citation-grounded 10-K"]
        UI["TenKSummaryCard<br/>inline UI · citation pills"]
        Evals["Eval harness<br/>smoke · full · offline"]
    end

    Cache[("SQLite cache · 24h TTL")]
    Anthropic["Anthropic Messages API"]

    C ==>|"Bearer JWT"| OAuth
    OAuth -.->|"401 + WWW-Authenticate"| C
    OAuth ==>|"authenticated"| Router
    Router --> EDGAR
    Router --> FRED
    Router --> Polygon
    Router --> Extractor
    Extractor --> UI
    Extractor ==>|"Sonnet 4.5 + Citations API"| Anthropic
    Evals ==>|"Opus 4.7 judge"| Anthropic
    Evals -.->|"replays tool calls"| Router
    EDGAR --> Cache
    FRED --> Cache
    Polygon --> Cache
    Extractor --> Cache

    classDef client fill:#15324f,stroke:#4f8cff,color:#eaf1ff
    classDef gate fill:#3a2c12,stroke:#ffb347,color:#ffe9c7
    classDef tool fill:#16233a,stroke:#2d3a4f,color:#dce6f5
    classDef key fill:#1d2f4d,stroke:#4f8cff,color:#eaf1ff
    classDef store fill:#16301f,stroke:#2ee08a,color:#d6f5e3
    classDef ext fill:#271d3d,stroke:#9b86ff,color:#ece6ff

    class C client
    class OAuth gate
    class Router,EDGAR,FRED,Polygon,UI tool
    class Extractor,Evals key
    class Cache store
    class Anthropic ext
```

| Node style | Meaning |
| --- | --- |
| Amber gate | OAuth 2.1 boundary — validated on every request |
| Blue (filled) | Citation-grounded extractor + eval harness — the audited paths |
| Green store | 24-hour SQLite response cache — keeps eval runs reproducible |
| Purple | External Anthropic Messages API (Sonnet 4.5 extract, Opus 4.7 judge) |

## Quickstart

```bash
git clone https://github.com/SebAustin/mcp-financial-data.git
cd mcp-financial-data
cp .env.example .env   # fill in API keys
make setup             # uv sync + pre-commit install
make ci                # lint + typecheck + tests + smoke eval (offline)
make serve             # run the MCP server on $MCP_HOST:$MCP_PORT
```

## What's in the box

| Surface | Tool / endpoint | Notes |
| --- | --- | --- |
| MCP tool | `edgar.list_filings` | Recent SEC filings for a CIK. |
| MCP tool | `edgar.company_facts` | XBRL facts (us-gaap concepts). |
| MCP tool | `fred.series` | FRED economic time series. |
| MCP tool | `polygon.aggregates` | OHLCV aggregate bars. |
| MCP tool | `tenk.extract_section` | Claude-grounded 10-K claims with citations. |
| MCP App | `tenk-summary-card` | Inline UI rendering the extractor output. |
| OAuth   | RFC 6750 resource server | Validates JWT against external IdP. |

## Eval targets (W1)

The eval harness writes per-case JSONL plus a summary JSON to
`evals/runs/<run_id>/`. CI runs `--smoke --offline` on every PR; nightly
CI runs `--full --budget 5 --min-judge-score 0.85` against live APIs.

| Metric | W1 target | W1 actual | Source of truth | Notes |
| --- | --- | --- | --- | --- |
| Smoke pass rate | 5 / 5 | **5 / 5** | `evals/cases/seed.jsonl` | Offline fixtures. |
| Mean exec-accuracy | ≥ 0.95 | **1.00** (offline) / **0.80** (live) | `evals/metrics.py::exec_accuracy` | Live MSFT XBRL multi-row list match — tracked in follow-on issues. |
| Mean citation coverage | = 1.00 | **1.00** | `evals/metrics.py::citation_coverage` | Required for `tenk.*`. |
| Mean judge score (offline) | ≥ 0.90 | **1.00** | `evals/metrics.py::judge_with_stub` | 0.5·exec + 0.5·citation. |
| Mean judge score (live full) | ≥ 0.85 | **0.93** | `evals/judge.py::judge_with_claude` | Opus 4.7 five-axis rubric. |
| P50 latency (smoke) | ≤ 50 ms | **< 1 ms** | harness `latency_ms` | Offline only. |
| Total cost / smoke run | $0.00 | **$0.00** | harness `total_cost_usd` | `--offline` enforced. |
| Total cost / live full run | ≤ $5.00 | **$0.08** | harness `total_cost_usd` | `--budget 5` gate. |
| Coverage gate (src/) | ≥ 85% | **~87%** | `pytest --cov-fail-under=85` | mypy `--strict` also gates. |

### Latest `--full` runs (git `b8a4ba3`, 2026-05-21)

Reproduce offline:

```bash
uv run python -m mcp_financial_data.evals.harness --full --offline
```

Reproduce live (requires `.env` secrets; ~$0.08 per run):

```bash
uv run python -m mcp_financial_data.evals.harness --full --budget 5 --min-judge-score 0.85
```

| Run | `run_id` | Pass | mean exec-acc | mean citation | mean judge | cost USD |
| --- | --- | --- | --- | --- | --- | --- |
| Offline full | `20260521T114816Z_b8a4ba3` | 5 / 5 | 1.00 | 1.00 | 1.00 | 0.00 |
| Live full | `20260521T114826Z_b8a4ba3` | 5 / 5 | 0.80 | 1.00 | 0.93 | 0.08 |

See [CHANGELOG.md](CHANGELOG.md) for the `v0.1.0` release notes.

## Hard constraints (skim before contributing)

- **Citations are non-optional** for the 10-K extractor. Every
  `CitedClaim.text` carries at least one `Citation`. Uncited model output
  is dropped or moved to `notes` with `[INFERENCE]`. See
  [`docs/adr/0003-citations-required-for-extracted-claims.md`](docs/adr/0003-citations-required-for-extracted-claims.md).
- **EDGAR Fair Access** is enforced. Every request carries the
  `EDGAR_USER_AGENT` env value. Process rate limit ≤ 10 req/sec.
- **Spend cap.** `MAX_API_SPEND_USD` defaults to 50. Enforced in extractor
  and harness.
- **No `requests`, no `print()`, no `subprocess shell=True`, no bare `except`.**
- **OAuth 2.1 RS only.** This server validates JWTs; it is never the IdP.
  See [`docs/adr/0004-oauth21-as-resource-server.md`](docs/adr/0004-oauth21-as-resource-server.md).

## Layout

```
src/mcp_financial_data/      # the package
  server.py                  # FastMCP entrypoint
  auth/oauth.py              # OAuth 2.1 RS primitives
  tools/{edgar,fred,polygon} # async API clients
  extractors/tenk.py         # citation-grounded 10-K extractor
  apps/ui.py                 # MCP Apps inline UI registration
  evals/{harness,metrics}    # eval harness (--smoke / --full / --offline)
tests/{unit,integration}     # pytest, 85% gate, integration skipped by default
evals/cases/seed.jsonl       # 5 hand-authored eval cases
evals/runs/                  # per-SHA harness output (gitignored)
docs/adr/                    # MADR architecture decisions
.github/                     # CI templates + issue/PR templates + dependabot
```

## References

1. [Model Context Protocol — specification 2025-11-25][mcp-spec]
2. [SEC EDGAR — accessing data fairly (User-Agent + 10/sec)][edgar-fair]
3. [FRED API documentation][fred-api]
4. [Polygon.io REST API][polygon-rest]
5. [Anthropic Citations API][anthropic-citations]

[mcp-spec]: https://modelcontextprotocol.io/specification/2025-11-25
[edgar-fair]: https://www.sec.gov/os/accessing-edgar-data
[fred-api]: https://fred.stlouisfed.org/docs/api/fred/
[polygon-rest]: https://polygon.io/docs/rest
[anthropic-citations]: https://docs.anthropic.com/en/docs/build-with-claude/citations

## License

MIT. See [LICENSE](LICENSE).
