"""Deterministic + LLM-judge metrics for the eval harness.

Per master rules §5: every metric is numeric, and any LLM-as-judge metric is
paired with at least one deterministic metric. We ship two:

- ``exec_accuracy``: deterministic. Fraction of expected output keys whose
  values exactly match the actual output. Range [0.0, 1.0].
- ``citation_coverage``: deterministic. ``cited_facts / total_facts``. Only
  meaningful for the 10-K extractor; returns 1.0 for non-extractor cases.
- ``judge_score``: LLM-as-judge in 0..5 (mapped to [0.0, 1.0] via /5.0).
  In offline mode, returns a deterministic stub score derived from
  ``exec_accuracy`` so CI is reproducible without an API key.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CaseMetrics:
    """Per-case metric bundle. Every field is numeric and optional-free."""

    exec_accuracy: float
    citation_coverage: float
    judge_score: float
    latency_ms: float
    cost_usd: float
    success: bool


def _values_match(expected: Any, actual: Any) -> bool:
    """Deep equality that ignores extra keys on dicts and list length must match."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        return all(k in actual and _values_match(v, actual[k]) for k, v in expected.items())
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return False
        return all(_values_match(e, a) for e, a in zip(expected, actual, strict=True))
    return bool(expected == actual)


def exec_accuracy(expected: dict[str, Any], actual: dict[str, Any]) -> float:
    """Deterministic match accuracy across keys present in ``expected``.

    Nested dicts and lists compare only the keys/elements in ``expected`` so
    tool models may include optional fields (e.g. ``primary_doc_description``)
    without penalizing the score. Returns 1.0 for an empty ``expected``.
    """
    if not expected:
        return 1.0
    matches = sum(1 for k, v in expected.items() if _values_match(v, actual.get(k)))
    return matches / len(expected)


def citation_coverage(actual: dict[str, Any]) -> float:
    """Fraction of extractor-shaped facts that carry at least one citation.

    Only applies to 10-K extractor output, identified by ``actual`` having a
    ``model`` key AND a ``facts`` list whose entries look like ``CitedClaim``
    (i.e. carry a ``text`` field). For all other shapes (EDGAR XBRL facts,
    FRED observations, Polygon bars), returns 1.0 so the metric does not
    penalize lookups whose schema has no citation concept.
    """
    if "model" not in actual:
        return 1.0
    facts = actual.get("facts")
    if not isinstance(facts, list) or not facts:
        return 1.0
    extractor_shaped = [f for f in facts if isinstance(f, dict) and "text" in f]
    if not extractor_shaped:
        return 1.0
    cited = sum(1 for f in extractor_shaped if f.get("citations"))
    return cited / len(extractor_shaped)


def judge_with_stub(case_id: str, exec_acc: float, cit_cov: float) -> float:
    """Deterministic offline judge.

    Returns ``round(0.5*exec_acc + 0.5*cit_cov, 4)``. Pure function, no env,
    no network, identical output for the same inputs. Only used when
    ``EVAL_OFFLINE=1`` or ``ANTHROPIC_API_KEY`` is unset.
    """
    _ = case_id
    return round(0.5 * exec_acc + 0.5 * cit_cov, 4)


async def judge_with_claude(
    case_id: str,
    expected: dict[str, Any],
    actual: dict[str, Any],
    *,
    model: str,
) -> float:
    """LLM-as-judge call against Claude.

    Delegates to :mod:`evals.judge`. The CI smoke slice uses ``judge_with_stub``
    because ``--offline`` is always set in CI.
    """
    from mcp_financial_data.evals.judge import judge_with_claude as _judge

    return await _judge(case_id, expected, actual, model=model)
