# Prompt 04 — MCP Apps inline UI for the 10-K summary

> Owns: `src/mcp_financial_data/apps/ui.py` and the matching React
> component shipped as a static resource. Read MCP spec 2025-11-25 §UI.

## Goal

When `tenk.extract_section` returns an `ExtractionResult`, the server
also emits an MCP Apps UI envelope so MCP clients (Claude Desktop, Cursor,
Goose) render the result inline as a `TenKSummaryCard` with citation pills
that open the source document on click.

## Acceptance

- `render_tenk_summary_card(props)` returns a JSON-serializable dict that
  validates against the MCP UI envelope schema.
- The envelope includes a content-addressed reference to the React bundle
  shipped under `static/ui/tenk-summary-card.bundle.js`.
- A `tests/unit/apps/test_ui.py` test renders the envelope for the
  `tenk-aapl-risk-factors` extraction and asserts:
  - `id == TENK_SUMMARY_CARD_ID`.
  - Each citation pill has the SEC filing URL pattern.
  - The bundle hash matches what's on disk.
- A `tests/integration/apps/test_ui_render.py` (skipped) launches the
  server, calls the tool from a real MCP client (FastMCP test client),
  and asserts the UI block ships.

## Implementation hints

- Build the React bundle in a separate `ui/tenk-summary-card/` workspace
  with esbuild; include it in the wheel via `pyproject.toml`'s
  `[tool.hatch.build.targets.wheel]` `force-include`.
- The component has 3 sections: Header (company / CIK / filing),
  FactsList (each with citation pills), Footer (model / cost / latency).
- Citations link via the SEC EDGAR filing URL convention:
  `https://www.sec.gov/cgi-bin/browse-edgar?...`.

## Files touched

- `src/mcp_financial_data/apps/ui.py`.
- `ui/tenk-summary-card/` (new TS workspace).
- `tests/unit/apps/test_ui.py` (extend).
- `docs/adr/0008-mcp-apps-bundle-distribution.md` (new ADR).
