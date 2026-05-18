---
title: "feat: ship MCP Apps inline UI (TenKSummaryCard) with citation pills"
labels: [enhancement, w1, ui]
assignees: [SebAustin]
---

## Problem

`apps/ui.py` registers a `TenKSummaryCard` placeholder. We need the
real MCP Apps inline UI per spec 2025-11-25, including a React bundle
shipped under `static/ui/tenk-summary-card.bundle.js` that renders the
extractor's `ExtractionResult` with one citation pill per fact. Clicking
a pill should open the SEC filing at the cited paragraph.

Build order: `prompts/04_mcp_apps_ui.md`. Decision: ADR 0008 (new — to
be added in this PR).

## Acceptance criteria

- [ ] `render_tenk_summary_card(props)` returns a JSON-serializable dict
  matching the MCP UI envelope schema.
- [ ] React bundle built with esbuild from `ui/tenk-summary-card/` and
  shipped via `[tool.hatch.build.targets.wheel]` `force-include`.
- [ ] Bundle hash recorded in the envelope and asserted by tests.
- [ ] `tests/unit/apps/test_ui.py` extended with a render assertion that
  validates the envelope schema and citation URLs.
- [ ] Integration test (skipped by default) shows the card rendering in
  Claude Desktop after `tenk.extract_section` is called.

## References

- https://modelcontextprotocol.io/specification/2025-11-25
- ADR 0008 (to be created in this PR)
