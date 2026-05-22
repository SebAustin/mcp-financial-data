# Video demo script — mcp-financial-data v0.1.0

**Length:** 90 seconds · **Format:** 5 scenes · **Windows:** browser + terminal

Prep once:

```bash
make demo-video        # smoke eval + preview HTML + checklist
make serve             # Terminal A — leave running
```

During recording, advance scenes with:

```bash
make demo-video-script   # full teleprompter (this file)
make demo-video-card     # Scene 2 — opens TenKSummaryCard in browser
make demo-video-audit    # Scene 3 — formatted eval metrics
make demo-video-oauth    # Scene 4 — labeled 401 → 200
```

---

## Scene 1 — The problem (0:00–0:15)

**Show:** README → **Why this exists** (first three bullets)

**Say:**

> Financial AI fails the same audit every time. The agent cites the wrong filing.
> It drops facts silently when the source doesn't support them. Or the MCP server
> never validated the JWT on the request. This repo fixes all three.

**Do:** Scroll slowly through bullets 1–3. Do not show `.env`.

---

## Scene 2 — Citation-grounded extraction (0:15–0:45)

**Show:** Browser — TenKSummaryCard for **Apple Inc. · AAPL 10-K Item 1A**

**Say:**

> `tenk.extract_section` pulls risk factors from a 10-K section. Claude Sonnet 4.5
> returns only citation-grounded facts — every claim you see on this card has at
> least one SEC reference. Uncited model output never appears here; it stays in
> `notes`.

**Do:**

1. Point at the two risk-factor bullets.
2. **Click one citation pill** → SEC EDGAR browse page opens.
3. Briefly show the footer: model id, tokens, cost, latency.

**Tip:** Use `make demo-video-card --serve` if `file://` renders oddly in your recorder.

---

## Scene 3 — Deterministic audit trail (0:45–1:05)

**Show:** Terminal — `make demo-video-audit`

**Say:**

> We don't trust vibes. The offline eval harness scores exec-accuracy, citation
> coverage, and a paired judge on every case. Smoke eval on this build: all ones,
> zero dollars, fully offline. CI runs the same gate on every pull request.

**Do:** Let the formatted metrics sit on screen for 5 seconds. Highlight the three
`1.0` scores and `offline: true`.

---

## Scene 4 — OAuth resource server (1:05–1:20)

**Show:** Terminal — `make demo-video-oauth` (with `make serve` running)

**Say:**

> Every HTTP request to `/mcp` carries a Bearer JWT. No token — RFC 6750 401 with
> `WWW-Authenticate`. Valid dev token — authorized. Production swaps the JWKS URL;
> the validation code path is the same.

**Do:** Run the command once. The script prints ✓ labels for **401** then **200**.
Do not paste the full token on camera.

---

## Scene 5 — Close (1:20–1:30)

**Show:** GitHub — green CI badge + eval-delta sticky comment on a recent PR

**Say:**

> mcp-financial-data — MCP spec 2025-11-25, SEC EDGAR, FRED, Polygon, OAuth 2.1,
> and citation-grounded 10-K extraction. Open source at
> github.com/SebAustin/mcp-financial-data.

---

## Recording setup

| Item | Recommendation |
| --- | --- |
| Resolution | 1080p, browser zoom 110% for citation pills |
| Windows | Browser left, terminal right (or switch cleanly — no overlapping chaos) |
| Mic | Wired; read at ~160 wpm |
| Takes | Three max; Scene 2 + 3 are fully offline and deterministic |
| Avoid | curl one-liners, live `--full` eval, `.env` on camera, theme switches |

## Optional Cursor scene (appendix, not in 90s cut)

If you want to show the MCP client inline UI instead of the browser preview:

1. Pre-connect Cursor to `http://127.0.0.1:8765` with `make -s oauth-dev` token.
2. Ask: *"Call tenk.extract_section for Apple Item 1A risk factors."*
3. Swap Scene 2 browser footage for the inline **TenKSummaryCard** in chat.

The browser preview uses the same offline fixture — same facts, same pills, zero API spend.

## After recording

1. Save to `recordings/demo-v0.1.0-<date>.mp4` (gitignored).
2. Paste the Loom/YouTube URL into [README.md](../../README.md) **Demo** section.
3. Pin the link on the GitHub repo **About** panel.
