---
title: "eval: track nightly full-eval green streak (3 consecutive days)"
labels: [eval, w2]
assignees: [SebAustin]
---

## Problem

W1 acceptance requires the nightly workflow to stay green for three
consecutive days. Today we only have a pass/fail badge with no streak
counter or regression alert.

## Acceptance criteria

- [ ] Nightly workflow uploads `summary.json` artifact and posts a job
  summary with `mean_judge_score`, `n_pass`, and `total_cost_usd`.
- [ ] Document the green-streak requirement in README (Eval targets).
- [ ] Optional: GitHub issue or discussion opened automatically when nightly
  fails twice in a row.

## References

- `.github/workflows/eval-nightly.yml`
- `prompts/05_evals_full_run.md`
