# ADR 0009 — LLM judge rubric and eval harness online dispatch

* Status: Accepted
* Date: 2026-05-20
* Deciders: Sebastien Henry

## Context and Problem Statement

The offline eval harness (fixtures + ``judge_with_stub``) is sufficient for CI
smoke, but it cannot detect regressions in real EDGAR/FRED/tenk integrations or
judge whether Claude outputs remain citation-grounded on live filings. Prompt 05
requires:

1. Online dispatch to real tools when ``--offline`` is not set.
2. ``judge_with_claude`` using Opus 4.7 with a numeric rubric.
3. ``--budget USD`` abort before spend runs away.
4. Nightly workflow exercising live APIs with secrets.

## Decision Drivers

* Master rules §5 — LLM judge paired with deterministic metrics.
* ``MAX_API_SPEND_USD`` already guards the extractor; the harness needs its
  own per-run ``--budget`` for multi-case suites.
* CI must stay offline; online paths are covered by ``respx`` in
  ``test_harness_live.py``.

## Decision Outcome

1. **``evals/dispatch.py``** — Maps ``case.tool`` to ``tools/*`` and
   ``extract_tenk_section``. Normalizes return shapes to match ``seed.jsonl``
   (e.g. wraps ``list_filings`` as ``{"filings": [...]}``).
2. **``evals/judge.py``** — ``judge_with_claude`` prompts Opus 4.7 for five
   integer axes (0–5): ``factual_accuracy``, ``citation_grounding``,
   ``completeness``, ``format_adherence``, ``latency_under_budget``. Stores
   ``judge_score = mean(axes) / 5``.
3. **``evals/types.py``** — Holds :class:`EvalCase` to avoid import cycles.
4. **Harness** — ``_run_one`` calls dispatch + judge when online; ``--budget``
   compares cumulative ``cost_usd`` (dispatch + judge, plus pre-check against
   extractor spend counter). Aborts with :class:`EvalBudgetExceededError` and a
   clear row error. Each case row records ``input_tokens``, ``output_tokens``,
   ``judge_input_tokens``, ``judge_output_tokens``, ``dispatch_cost_usd``, and
   ``judge_cost_usd``. The summary row records ``model_primary``,
   ``model_judge``, and token totals.
5. **Nightly** — ``eval-nightly.yml`` runs ``--full --budget 5
   --min-judge-score 0.85`` with ``EVAL_OFFLINE=0`` and repository secrets;
   artifacts uploaded for trend review. The workflow badge reflects pass/fail.

## Consequences

* Full live runs cost real API credits; nightly caps via ``MAX_API_SPEND_USD=5``.
* Judge scores are reproducible only when model + prompt are pinned; JSON-only
  judge responses are validated strictly.
* ``tenk.extract_section`` online eval uses offline fixture text in the seed case
  to keep nightly cost bounded (still calls Anthropic for real citations).

## References

* ``prompts/05_evals_full_run.md``
* ADR 0003 — Citations required
* ADR 0007 — Extractor pricing + spend cap
