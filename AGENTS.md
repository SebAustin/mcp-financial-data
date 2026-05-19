# AGENTS.md

Pointer file for any AI agent (Cursor, Claude Code, Codex) opening this repo.

## Read these first, in order

1. `.cursorrules` — master portfolio rules + project deltas. Non-optional.
2. `docs/adr/` — every architectural decision is captured here in MADR.
3. `evals/harness.py` — the source of truth for "is this thing working".

## What this repo is

An MCP server (spec 2025-11-25) that exposes SEC EDGAR + FRED + Polygon
financial data with OAuth 2.1, plus a Claude-powered 10-K extractor that
returns citation-grounded claims, plus an MCP Apps inline UI component.

Anchor audience: Anthropic Forward Deployed Engineering, Bridgewater /
Citadel / Anthropic Finance teams.

## Hard constraints (skim before generating code)

- **Citations:** Every claim from the 10-K extractor must carry an Anthropic
  Citations API reference. Uncited claims are dropped.
- **EDGAR Fair Access:** Every EDGAR call needs a contact User-Agent and the
  process is rate-limited to ≤ 10 req/sec.
- **Spend cap:** `MAX_API_SPEND_USD` env var is enforced in the extractor and
  the eval harness. CI runs `--offline`.
- **OAuth 2.1:** This server is the resource server. Validate JWTs against
  the configured JWKS; never hardcode public keys.
- **No `requests`, no `print()`, no `subprocess shell=True`, no bare `except`.

## What "done" looks like for the W1 sprint

- `make ci` exits 0 (lint + typecheck + test ≥85% + smoke eval).
- A 60-second Loom demo of: OAuth round-trip → MCP tool call → 10-K extract
  with visible citation pills → MCP Apps inline UI rendering.
- README.md eval table populated with real numbers from a `--full` run.
- Tag `v0.1.0`, three GitHub issues filed for follow-on work, applications
  to Anthropic FDE + Cursor FDE sent.
