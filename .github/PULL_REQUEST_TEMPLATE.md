<!--
Thanks for the PR. Tick the boxes the change actually exercises; remove the
section if it doesn't apply.
-->

## What
<!-- One paragraph summary. -->

## Why
<!-- Closes #N or links to context. -->

## Eval delta
<!--
Paste the relevant fields from `evals/runs/<run_id>/summary.json`:

```json
{
  "mean_exec_accuracy": ...,
  "mean_citation_coverage": ...,
  "mean_judge_score": ...,
  "mean_latency_ms": ...,
  "total_cost_usd": ...
}
```
-->

## Checklist
- [ ] `make ci` is green locally
- [ ] Tests added/updated under `tests/unit/`
- [ ] Eval cases added/updated under `evals/cases/seed.jsonl` if behaviour-changing
- [ ] ADR added under `docs/adr/` if this changes architecture
- [ ] No new secrets or hardcoded credentials
- [ ] Docs / README updated where the change is user-visible
