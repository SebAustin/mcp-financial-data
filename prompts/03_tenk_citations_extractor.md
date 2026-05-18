# Prompt 03 — Citation-grounded 10-K extractor

> Owns: `src/mcp_financial_data/extractors/tenk.py` and matching tests.
> Read `.cursor/rules/citations.mdc` and ADR 0003 first.

## Goal

`extract_tenk_section(section, *, settings, max_tokens)` calls Claude
Sonnet 4.5 with the Anthropic Citations API and returns an
`ExtractionResult` whose `facts` are `CitedClaim` objects with
`citations` populated by the API. Uncited model output goes into `notes`
prefixed `[INFERENCE]`.

## Acceptance

- Every `CitedClaim` in `result.facts` has at least one `Citation`.
- `result.cost_usd` is the sum of input + output token cost using the
  current Sonnet pricing table (constant in `extractors/tenk.py`).
- The spend-cap path stays — if `MAX_API_SPEND_USD` is hit before this
  call, raise `ExtractorSpendCapError`.
- The eval case `tenk-aapl-risk-factors` passes with
  `citation_coverage = 1.0` against a `respx`-mocked Anthropic response
  AND against the real API (nightly).
- `tests/unit/extractors/test_tenk.py` extended with:
  - happy-path mock returning two cited claims.
  - mock returning one cited and one uncited block; assert uncited goes
    to `notes` and is NOT in `facts`.
  - mock returning a citation whose `cited_text` does not appear in the
    source document; assert that fact is dropped.
  - spend-cap test still passes.

## Implementation hints

- Use `anthropic.AsyncAnthropic` from the SDK.
- Pass each section as one `document` content block:
  `{"type": "document", "source": {"type": "text", "media_type": "text/plain",
  "data": section.text}, "title": section.document_title,
  "context": "10-K Item 1A risk factor section",
  "citations": {"enabled": True}}`.
- For multi-section documents, pass multiple `document` blocks in the
  same request — Claude will cite across sections.
- Parse the response: each text block carries an array of `citations`;
  group consecutive same-citation blocks into one `CitedClaim`.
- Use `tenacity` for transient 429 / 5xx retries; max 3, wait ≤ 8s.

## Files touched

- `src/mcp_financial_data/extractors/tenk.py`.
- `src/mcp_financial_data/extractors/_pricing.py` (new — token pricing
  table, dataclass).
- `tests/unit/extractors/test_tenk.py` (extend).
- `docs/adr/0007-extractor-pricing-and-spend-cap.md` (new ADR).
