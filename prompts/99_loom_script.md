# Loom script — mcp-financial-data v0.1.0

> Target length: **60 seconds**. Three takes max (cut-bait rule §A.5).
> Record at 1080p with OBS or Loom desktop. Audio with a wired mic.

## Scene timings

| Time | Scene | Voiceover | Visual |
| --- | --- | --- | --- |
| 0:00–0:08 | Title card | "mcp-financial-data is an MCP server for SEC EDGAR, FRED, and Polygon, with a citation-grounded 10-K extractor." | Static title with the architecture mermaid diagram. |
| 0:08–0:18 | OAuth handshake | "MCP client connects, OAuth 2.1 with PKCE, JWT validated against the configured JWKS." | Terminal: `make oauth-dev` then a `curl` with `Authorization: Bearer ...` and a 200 response. |
| 0:18–0:35 | Tool call | "I call `tenk.extract_section` on Apple's most recent 10-K Item 1A. Claude Sonnet 4.5 returns four facts, each tied back to the source filing via the Anthropic Citations API." | Claude Desktop: paste filing, get back the inline `TenKSummaryCard` with citation pills. Hover one — opens the SEC filing at the right paragraph. |
| 0:35–0:48 | Audit trail | "Every fact carries at least one citation. Uncited model output is dropped — never surfaced as a fact. The JSONL eval row records exec-accuracy 1.0 and citation coverage 1.0." | Terminal: `tail -1 evals/runs/<sha>/summary.json` showing the green numbers. |
| 0:48–0:60 | Close | "CI runs the smoke eval offline on every PR. Nightly runs the full suite live with a $5 spend cap. Five cases, all green. Repo's pinned at github.com/SebAustin/mcp-financial-data." | GitHub PR view with the sticky eval-delta comment + green CI checks. |

## Voiceover script (read at 175 wpm)

> "mcp-financial-data is an MCP server — spec 2025-11-25 — for SEC EDGAR,
> FRED, and Polygon, with a citation-grounded 10-K extractor.
>
> The MCP client connects over OAuth 2.1 with PKCE. JWTs are validated
> against the configured JWKS — wrong audience or expired token gets a
> standards-clean 401 with `WWW-Authenticate: Bearer error=invalid_token`.
>
> I'll call `tenk.extract_section` on Apple's latest 10-K Item 1A. Claude
> Sonnet 4.5 returns four risk factors, each tied back to the source
> filing via Anthropic's Citations API. Hover any pill — it opens the
> SEC filing at the cited paragraph.
>
> Every fact carries at least one citation; uncited model output is
> dropped, never surfaced as a fact. The eval JSONL row records
> exec-accuracy 1.0 and citation coverage 1.0.
>
> CI runs the smoke eval offline on every PR. Nightly runs the full
> suite against live APIs with a five-dollar spend cap. Five cases,
> all green. Repo at github.com/SebAustin/mcp-financial-data."

## Anti-patterns to avoid

- Don't show your eval secrets / `.env`.
- Don't run `--full` in front of the camera (latency variance ruins
  the timing).
- Don't switch IDE color schemes mid-recording.
- Don't say "as you can see" — show, don't tell.
- Don't apologize for typos. Cut and re-record the section in OBS.

## Outputs

- `recordings/loom-v0.1.0-<date>.mp4` (gitignored).
- Loom link pasted into the README and the LinkedIn post.
- 30-second silent GIF of the OAuth → tool call → UI render scene
  (export from OBS) for embed in the LinkedIn post.
