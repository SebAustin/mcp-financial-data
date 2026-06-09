# Video demo script — mcp-financial-data v0.1.0

**Length:** 2 minutes · **Format:** 4 slides · **Window:** single browser tab

## Before you roll

```bash
make demo-start
```

This runs an offline smoke eval, builds the story hub, opens `http://127.0.0.1:8766/index.html`, and prints teleprompter cues in the terminal.

Advance slides with **← →** arrow keys or click the numbered dots.

---

## Slide 1 — The ask (0:00–0:20)

**Show:** Mock analyst chat + `tenk.extract_section` chip

**Say:**

> A compliance analyst is preparing a diligence memo on Apple. They ask the MCP
> client for supply chain and macroeconomic risks from 10-K Item 1A — and they
> need every claim tied to the filing, not model paraphrase.

**Do:** Read the bubble on screen. Point at the tool chip.

---

## Slide 2 — The answer (0:20–1:05)

**Show:** TenKSummaryCard — Apple Inc. · AAPL 10-K Item 1A

**Say:**

> The server calls `tenk.extract_section`. Claude Sonnet 4.6 returns only
> citation-grounded facts via the Citations API. Every bullet on this card has
> at least one SEC reference. Uncited model output never appears here.

**Do:**

1. Point at the two risk-factor bullets.
2. **Click a citation pill** — SEC EDGAR browse page opens.
3. Briefly show the footer: model, tokens, cost, latency.

---

## Slide 3 — The proof (1:05–1:35)

**Show:** Split panel — `[INFERENCE]` note vs cited facts + eval metrics

**Say:**

> Speculative output stays in notes, tagged INFERENCE — never surfaced as a
> fact. The offline eval harness scores exec-accuracy, citation coverage, and
> a paired judge. On this build: all ones, zero dollars, fully offline. CI
> runs the same smoke gate on every pull request.

**Do:** Gesture left (bad) then right (good). Pause on the three **1.0** metrics.

---

## Slide 4 — The stack (1:35–2:00)

**Show:** Architecture strip + green CI badge + repo link

**Say:**

> mcp-financial-data — MCP spec 2025-11-25. OAuth 2.1 resource server, SEC
> EDGAR, FRED, Polygon, citation-grounded 10-K extraction, and MCP Apps inline
> UI. Open source at github.com/SebAustin/mcp-financial-data.

**Do:** Let the CI badge and repo link sit on screen for the close.

---

## Recording setup

| Item | Recommendation |
| --- | --- |
| Command | `make demo-start` only — no terminal switching on camera |
| Resolution | 1080p; browser zoom 100–110% |
| Navigation | Arrow keys between slides; rehearse pill click on Slide 2 |
| Takes | Three max; Slides 1–3 are fully offline and deterministic |
| Avoid | `.env` on camera, live `--full` eval, OAuth terminal scenes |

## Appendix — live Cursor MCP (optional)

See [`cursor-mcp-setup.md`](cursor-mcp-setup.md) if you want to swap Slide 2 for a live
Cursor inline **TenKSummaryCard** instead of the browser hub.

## After recording

1. Save to `recordings/demo-v0.1.0-<date>.mp4` (gitignored).
2. Paste the Loom/YouTube URL into [README.md](../../README.md) **Demo** section.
3. Pin the link on the GitHub repo **About** panel.
