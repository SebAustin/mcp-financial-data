---
title: "bug: exec_accuracy under-scores company_facts when filter returns multiple rows"
labels: [bug, eval, w2]
assignees: [SebAustin]
---

## Problem

Live `edgar-msft-revenues-fy2025` can return several FY2025 rows for
`RevenueFromContractWithCustomerExcludingAssessedTax`. Deterministic
`exec_accuracy` requires an exact list length match against `expected`, so
the case scores `0.0` even when the judge confirms the correct fact is
present.

## Acceptance criteria

- [ ] `exec_accuracy` (or a company-facts-specific helper) matches when
  `expected.xbrl_facts` is a subset of `actual.xbrl_facts` by concept,
  fiscal year, and value tolerance.
- [ ] Unit tests in `tests/unit/evals/test_metrics.py` cover multi-row
  company-facts payloads.
- [ ] Live `--full` run reports `mean_exec_accuracy >= 0.95` without
  lowering judge scores.

## References

- `src/mcp_financial_data/evals/metrics.py`
- `src/mcp_financial_data/evals/dispatch.py::_filter_xbrl_facts_for_eval`
