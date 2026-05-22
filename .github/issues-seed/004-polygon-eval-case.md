---
title: "feat: add polygon.aggregates eval case to seed.jsonl"
labels: [feat, eval, w2]
assignees: [SebAustin]
---

## Problem

`polygon.aggregates` is registered on the MCP server but absent from
`evals/cases/seed.jsonl`. Nightly `--full` never exercises the Polygon client,
so regressions there would not move eval metrics.

## Acceptance criteria

- [ ] New case `polygon-aapl-daily-2025` in `evals/cases/seed.jsonl` with
  offline fixture and live expected values.
- [ ] `evals/dispatch.py` route already exists; extend judge compaction if
  bar payloads are large.
- [ ] Offline and live `--full` runs pass with `n_pass == n_cases`.
- [ ] README eval table updated with the new case count.

## References

- `src/mcp_financial_data/tools/polygon.py`
- ADR 0009 — eval harness online dispatch
