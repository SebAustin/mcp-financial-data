# Prompt 05 — Evals: live-network mode + LLM judge

> Owns: `src/mcp_financial_data/evals/harness.py` (online dispatch) and
> `evals/metrics.py::judge_with_claude`.

## Goals

1. In non-`--offline` mode, the harness dispatches each case to the real
   tool implementation (built in prompts 02–04) instead of reading
   `OFFLINE_FIXTURES`.
2. `judge_with_claude(case_id, expected, actual, *, model)` calls Claude
   Opus 4.7 with a 5-axis rubric and returns a 0..1 score.
3. The eval harness records: model id, judge model id, input/output
   tokens, $ cost per case, and a `--budget USD` flag that aborts the
   run if the running total exceeds the budget.
4. The nightly workflow (`.github/workflows/eval-nightly.yml`) reports a
   green/red badge and uploads the per-SHA artifact.

## Acceptance

- `EVAL_OFFLINE=0 uv run python -m mcp_financial_data.evals.harness --full`
  with valid secrets returns `n_pass=5, n_cases=5` and
  `mean_judge_score >= 0.85` against the real APIs.
- `--budget 2.50` aborts the run with a clean error if cost exceeds $2.50
  before completion.
- `tests/unit/evals/test_harness_live.py` adds `respx`-mocked end-to-end
  tests of the online dispatch path.
- The nightly workflow runs and stays green for 3 consecutive days.

## Implementation hints

- Add an `online` dispatch table keyed by `case.tool` to functions that
  call the real `tools/*` and `extractors/*` clients.
- Stream Anthropic responses where possible to keep token attribution
  accurate per chunk.
- Use `judge_with_claude`'s rubric: `factual_accuracy`,
  `citation_grounding`, `completeness`, `format_adherence`,
  `latency_under_budget`.

## Files touched

- `src/mcp_financial_data/evals/harness.py`.
- `src/mcp_financial_data/evals/judge.py` (new — Anthropic judge).
- `tests/unit/evals/test_harness_live.py` (new).
- `docs/adr/0009-llm-judge-rubric-and-replayability.md` (new ADR).
