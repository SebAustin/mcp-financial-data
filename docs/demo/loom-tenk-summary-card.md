# Loom demo script — TenK Summary Card (MCP Apps)

Target length: **~60 seconds**. Record after PR #10 is on `main` and secrets are loaded.

## Prerequisites

```bash
cp .env.example .env
# Set: ANTHROPIC_API_KEY, EDGAR_USER_AGENT="Your Name <you@example.com>"
make serve
```

In Cursor (or Claude Desktop), add the MCP server URL from `.env` (`MCP_HOST` / `MCP_PORT`).
Complete the OAuth dev round-trip if prompted:

```bash
make oauth-dev   # paste Bearer token when the client asks
```

## Beat sheet (60s)

| Time | On screen | Narration |
|------|-----------|-----------|
| 0–10s | Cursor MCP settings → connected server | "Streamable-HTTP MCP server with OAuth 2.1 resource-server validation." |
| 10–25s | Tool list showing `tenk.extract_section` | "Tool advertises `ui://mcp-financial-data/tenk-summary-card` for inline rendering." |
| 25–45s | Call `tenk.extract_section` with Apple CIK + Item 1A snippet | "Extractor uses Anthropic Citations API — every fact carries a citation." |
| 45–55s | **TenKSummaryCard** inline: header, facts, citation pills | "Click a pill — SEC EDGAR browse URL. Footer shows model, tokens, cost, latency." |
| 55–60s | Expand one citation / show `resources/read` in logs (optional) | "Bundle ships via `resources/read` and content-addressed SHA-256 in the envelope." |

## Sample tool arguments

```json
{
  "cik": "0000320193",
  "company_name": "Apple Inc.",
  "section": {
    "section": "item_1a_risk_factors",
    "document_title": "AAPL 10-K FY2025 Item 1A",
    "text": "The Company's business depends on the timely receipt of components from third-party manufacturers and is exposed to global macroeconomic conditions, including inflation and foreign exchange fluctuations."
  }
}
```

## What to highlight

1. **Citation pills** — each links to `https://www.sec.gov/cgi-bin/browse-edgar?...`
2. **No uncited facts** — `[INFERENCE]` items stay in `notes`, not the card
3. **Spend cap** — mention `MAX_API_SPEND_USD` if you hit the limit during recording

## Post-recording

- Link the Loom in README.md under a "Demo" section
- Paste one smoke eval row from `evals/runs/*/summary.jsonl` into the README eval table
