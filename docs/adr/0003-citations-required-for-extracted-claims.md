# ADR 0003 — Citations are required for every extracted 10-K claim

* Status: Accepted
* Date: 2026-05-17
* Deciders: Sebastien Henry

## Context and Problem Statement

The 10-K extractor will be the most-watched code path in this repo. Every
hiring manager from Anthropic Finance to Bridgewater research will paste a
real 10-K excerpt and ask: "where did the model get this?" If the answer is
"the model said so", the demo is over.

## Decision Drivers

* Master `.cursorrules` §7 mandates that user-facing claims tied to source
  documents go through the Anthropic Citations API.
* SEC 17a-4 / FINRA 4511 retention requirements expect verifiable lineage
  from any model-generated artifact to the source filing.
* The eval harness needs a deterministic, numeric "citation coverage"
  metric to gate regressions.

## Considered Options

* **Hard-require citations.** Drop or demote uncited spans.
* **Cite when convenient.** Mark uncited spans `[INFERENCE]` and surface
  them as facts with a warning. Loose; failure mode is cited drift.
* **Post-hoc string matching against the source.** Brittle; misses
  paraphrase; not what `Citations API` was designed for.

## Decision Outcome

Hard-require citations:

1. Every fact in `ExtractionResult.facts` is a `CitedClaim` with at least
   one `Citation`.
2. Uncited model output is either dropped or moved to `notes` prefixed
   with `[INFERENCE]` — never returned as a fact.
3. The eval harness records `citation_coverage = cited_facts / total_facts`
   per case and the smoke slice asserts coverage = 1.0 for the extractor.
4. Tests under `tests/unit/extractors/` assert the contract: every
   `CitedClaim` has at least one citation, and `cited_text` actually
   appears in the source document.

## Consequences

* The extractor's effective recall is lower than a free-text model, by
  design.
* When Anthropic's Citations API itself misses, the extractor surfaces
  fewer facts rather than more uncited ones — a desirable failure mode.
* The MCP Apps UI renders citation pills next to each claim, opening the
  source document inline.

## References

* https://docs.anthropic.com/en/docs/build-with-claude/citations
* `.cursor/rules/citations.mdc` (project-local enforcement).
