# Loom demo — mcp-financial-data v0.1.0

Target length: **60 seconds**. Three takes max. Record at 1080p (OBS or Loom
desktop). Use a wired mic.

## Prep (run before rolling)

```bash
make demo-prep   # smoke eval + prints copy-paste terminal commands
```

Ensure `.env` has at least:

- `ANTHROPIC_API_KEY` (only if you demo a **live** extractor call; offline eval
  does not need it)
- `MCP_OAUTH_DEV_SECRET` (any local-only string) for `make oauth-dev`
- `EDGAR_USER_AGENT="Your Name <you@example.com>"` if you hit EDGAR tools on camera

```bash
# Terminal A
make serve

# Terminal B — follow the commands printed by make demo-prep
```

Connect Cursor or Claude Desktop to `http://127.0.0.1:8765` (or your
`MCP_HOST` / `MCP_PORT`). Paste the dev Bearer token when prompted.

## Scene timings

| Time | Scene | Voiceover | Visual |
| --- | --- | --- | --- |
| 0:00–0:08 | Title | MCP server for SEC EDGAR, FRED, and Polygon with a citation-grounded 10-K extractor. | README architecture diagram (Sonnet 4.5 extractor + Opus 4.7 eval judge). |
| 0:08–0:18 | OAuth | MCP client connects over OAuth 2.1; JWTs validated against JWKS (dev HS256 locally). | `make oauth-dev`, then `curl` without token → **401**, with token → authorized **POST /mcp**. |
| 0:18–0:35 | Tool call | Call `tenk.extract_section` on AAPL Item 1A. Claude Sonnet 4.5 returns citation-grounded facts via the Citations API. | Inline **TenKSummaryCard**: hover a pill → SEC EDGAR browse URL. |
| 0:35–0:48 | Audit trail | Every surfaced fact has citations; uncited spans stay in `notes`. Smoke eval records exec-accuracy and citation coverage at 1.0 offline. | `cat evals/runs/<latest>/summary.json` from `make demo-prep`. |
| 0:48–0:60 | Close | CI smoke eval on every PR; nightly full eval live with a $5 cap. Repo: github.com/SebAustin/mcp-financial-data. | GitHub Actions green + sticky eval-delta PR comment. |

## Voiceover (read at ~175 wpm)

> mcp-financial-data is an MCP server — spec 2025-11-25 — for SEC EDGAR,
> FRED, and Polygon, with a citation-grounded 10-K extractor.
>
> The MCP client connects over OAuth 2.1. JWTs are validated against the
> configured JWKS — wrong audience or an expired token returns a
> standards-clean 401 with `WWW-Authenticate: Bearer error=invalid_token`.
>
> I'll call `tenk.extract_section` on Apple's 10-K Item 1A. Claude Sonnet
> 4.5 returns citation-grounded risk factors tied to the source filing.
> Hover any pill — it opens the SEC filing at the cited passage.
>
> Every fact on the card carries at least one citation; uncited model output
> is dropped, never surfaced as a fact. The smoke eval summary records
> exec-accuracy 1.0 and citation coverage 1.0 offline.
>
> CI runs the smoke eval on every PR. Nightly runs the full suite against
> live APIs with a five-dollar spend cap. Repo at
> github.com/SebAustin/mcp-financial-data.

## Sample `tenk.extract_section` arguments

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

1. **Citation pills** — SEC `cgi-bin/browse-edgar` URLs from `apps/ui.py`
2. **Footer** — model id, token counts, cost, latency
3. **No uncited facts on the card** — `[INFERENCE]` items remain in `notes`

## Anti-patterns

- Do not show `.env` or API keys on camera.
- Do not run `--full` live on camera (latency variance breaks timing).
- Do not switch IDE themes mid-recording.

## After recording

1. Save video to `recordings/loom-v0.1.0-<date>.mp4` (gitignored).
2. Paste the Loom URL into [README.md](../../README.md) **Demo** section.
3. Pin the Loom link in the GitHub repo **About** panel.
4. Optional: export a 30s silent GIF (OAuth → tool call → UI) for LinkedIn.
