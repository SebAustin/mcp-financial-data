# ADR 0008 — MCP Apps bundle distribution for TenKSummaryCard

* Status: Accepted
* Date: 2026-05-20
* Deciders: Sebastien Henry

## Context and Problem Statement

Prompt 04 requires an MCP Apps inline UI that renders ``ExtractionResult`` output
with citation pills linking to SEC EDGAR. Hosts (Claude Desktop, Cursor, Goose)
expect:

1. A tool metadata reference to a predeclared ``ui://`` resource (SEP-1865).
2. A shipped JavaScript bundle the host loads inside a sandboxed iframe.
3. A server-side **UI envelope** the tool returns alongside structured data so
   clients can render without guessing props shape.

## Decision Drivers

* ADR 0002 pins MCP spec 2025-11-25 including MCP Apps.
* The demo must show citation pills with ``cgi-bin/browse-edgar`` URLs.
* CI cannot depend on a private npm registry (Indeed Artifactory); the bundle
  must be buildable locally but is also committed so ``pytest`` passes without
  ``npm ci``.

## Decision Outcome

1. **Envelope builder** — ``apps/ui.py::render_tenk_summary_card`` returns a
   pydantic-validated :class:`McpUiEnvelope` with ``type="ui"``, stable
   ``id=tenk-summary-card``, ``resourceUri=ui://mcp-financial-data/tenk-summary-card``,
   ``mimeType=text/html;profile=mcp-app``, serialized props, citation pills,
   and a :class:`UiBundleReference` carrying ``path``, ``uri``, and ``sha256``.
2. **Bundle location** — Source lives under ``ui/tenk-summary-card/`` (React +
   esbuild). The committed artifact is ``static/ui/tenk-summary-card.bundle.js``.
   Hatch ``force-include`` copies ``static/ui`` into the wheel at
   ``mcp_financial_data/static/ui`` for installed packages.
3. **Tool wiring** — ``tenk.extract_section`` returns :class:`TenKExtractOutput`
   (``extraction`` + ``ui``) and registers ``meta.ui.resourceUri`` on the tool.
4. **SEC URLs** — Pills use ``sec_edgar_browse_url(cik)`` →
   ``https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=...``.

## Consequences

* Rebuilding the UI requires ``make ui-build`` when npm registry access is
  available; otherwise edit the committed bundle and refresh ``sha256`` tests.
* Eval cases for ``tenk.extract_section`` still compare ``ExtractionResult``
  fields only; the UI envelope is not part of ``exec_accuracy`` today.
* FastMCP ``call_tool`` integration tests assert tool advertisement, not live
  Anthropic extraction, to keep ``@pytest.mark.integration`` lean.

## References

* https://modelcontextprotocol.io/extensions/apps/overview
* SEP-1865 — MCP Apps
* ``prompts/04_mcp_apps_ui.md``
