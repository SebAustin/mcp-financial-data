---
title: "feat: implement Claude 10-K extractor with Anthropic Citations API (drop uncited spans)"
labels: [enhancement, w1, citations]
assignees: [SebAustin]
---

## Problem

`extractors/tenk.py` is currently a typed stub. We need the live
implementation that calls Claude Sonnet 4.5 with the Anthropic Citations
API (`citations={"enabled": True}`) and returns `CitedClaim` objects, each
carrying at least one `Citation`.

Hard contract (ADR 0003 + `.cursor/rules/citations.mdc`):

1. Every `CitedClaim.text` carries at least one `Citation`.
2. Uncited model output is dropped or moved to `notes` with `[INFERENCE]`.
3. `cited_text` must actually appear in the source document; otherwise
   the claim is dropped.
4. `MAX_API_SPEND_USD` cap is enforced; the existing `ExtractorSpendCapError`
   path stays.

Build order: `prompts/03_tenk_citations_extractor.md`.

## Acceptance criteria

- [ ] `extract_tenk_section` returns an `ExtractionResult` whose `facts`
  are `CitedClaim` objects with non-empty `citations`.
- [ ] Cost accounting populates `input_tokens`, `output_tokens`, and
  `cost_usd` correctly using the pricing table in
  `extractors/_pricing.py` (new in this PR).
- [ ] `tests/unit/extractors/test_tenk.py` extended:
  - happy-path (all cited),
  - mixed (some uncited, demoted to `notes`),
  - drift (cited_text not in source, dropped),
  - spend cap (existing test stays).
- [ ] Eval case `tenk-aapl-risk-factors` passes against a `respx`-mocked
  Anthropic response with `citation_coverage = 1.0`.
- [ ] Nightly eval against the live API passes for 3 consecutive nights.

## References

- https://docs.anthropic.com/en/docs/build-with-claude/citations
- ADR 0003 (`docs/adr/0003-citations-required-for-extracted-claims.md`)
- `.cursor/rules/citations.mdc`
