"""LLM-as-judge for the eval harness (Claude Opus 4.7).

Paired with deterministic metrics per master rules §5. The rubric scores five
axes on a 0-5 scale; the harness stores ``judge_score = mean_axis / 5.0``.

See ``docs/adr/0009-llm-judge-rubric-and-replayability.md``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Final

import anthropic
from anthropic.types import TextBlock
from pydantic import BaseModel, ConfigDict, Field

from mcp_financial_data.extractors._pricing import (
    UnknownModelPricingError,
    estimate_cost_usd,
    resolve_api_model_id,
)
from mcp_financial_data.logging import get_logger
from mcp_financial_data.settings import Settings, get_settings

_log = get_logger("eval.judge")

RUBRIC_AXES: Final[tuple[str, ...]] = (
    "factual_accuracy",
    "citation_grounding",
    "completeness",
    "format_adherence",
    "latency_under_budget",
)

_JUDGE_MAX_JSON_CHARS: Final[int] = 120_000

_JUDGE_SYSTEM: Final[str] = (
    "You are an eval judge for a financial MCP server. Score the ACTUAL tool "
    "output against EXPECTED reference data on five axes from 0 to 5 "
    "(integers only). Return ONLY a JSON object with those five keys and "
    "integer values. No prose."
)


class JudgeScoreError(Exception):
    """Raised when the judge model returns an unparseable response."""


@dataclass(frozen=True, slots=True)
class JudgeOutcome:
    """Result of one ``judge_with_claude`` call, including token attribution."""

    score: float
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class JudgeRubricScores(BaseModel):
    """Five-axis rubric returned by the judge model."""

    model_config = ConfigDict(extra="forbid")

    factual_accuracy: int = Field(..., ge=0, le=5)
    citation_grounding: int = Field(..., ge=0, le=5)
    completeness: int = Field(..., ge=0, le=5)
    format_adherence: int = Field(..., ge=0, le=5)
    latency_under_budget: int = Field(..., ge=0, le=5)

    def normalized(self: JudgeRubricScores) -> float:
        """Map the mean axis score to [0.0, 1.0]."""
        total = (
            self.factual_accuracy
            + self.citation_grounding
            + self.completeness
            + self.format_adherence
            + self.latency_under_budget
        )
        return round(total / (len(RUBRIC_AXES) * 5.0), 4)


def compact_for_judge(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    """Shrink large tool payloads before the Opus judge call."""
    compact: dict[str, Any] = dict(actual)
    facts = compact.get("xbrl_facts")
    if isinstance(facts, list):
        expected_rows = expected.get("xbrl_facts")
        if isinstance(expected_rows, list) and expected_rows:
            concepts = {
                str(row["concept"])
                for row in expected_rows
                if isinstance(row, dict) and row.get("concept") is not None
            }
            fiscal_years = {
                int(row["fiscal_year"])
                for row in expected_rows
                if isinstance(row, dict) and row.get("fiscal_year") is not None
            }
            filtered = facts
            if concepts:
                filtered = [
                    row
                    for row in filtered
                    if isinstance(row, dict) and row.get("concept") in concepts
                ]
            if fiscal_years:
                filtered = [
                    row
                    for row in filtered
                    if isinstance(row, dict) and row.get("fiscal_year") in fiscal_years
                ]
            compact["xbrl_facts"] = filtered[:50]
        elif len(facts) > 50:
            compact["xbrl_facts"] = facts[:50]
            compact["_truncated"] = True
    if len(json.dumps(compact, sort_keys=True)) > _JUDGE_MAX_JSON_CHARS:
        for key, value in list(compact.items()):
            if isinstance(value, list) and len(value) > 20:
                compact[key] = value[:20]
        compact["_truncated"] = True
    return compact


def _extract_json_object(text: str) -> dict[str, Any]:
    """Parse the first JSON object from model text."""
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[^{}]*\}", text, flags=re.DOTALL)
    if match is None:
        raise JudgeScoreError(f"judge returned no JSON object: {text[:200]!r}")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise JudgeScoreError("judge JSON was not an object")
    return data


async def judge_with_claude(
    case_id: str,
    expected: dict[str, Any],
    actual: dict[str, Any],
    *,
    model: str,
    settings: Settings | None = None,
    latency_ms: float = 0.0,
    budget_ms: float | None = None,
) -> JudgeOutcome:
    """LLM-as-judge call against Claude.

    Returns a :class:`JudgeOutcome` with normalized score, model id, token
    counts, and USD cost computed from the pricing table.
    """
    s = settings or get_settings()
    if s.anthropic_api_key is None:
        raise JudgeScoreError("ANTHROPIC_API_KEY is required for judge_with_claude")

    latency_hint = (
        f"latency_ms={latency_ms:.1f}, budget_ms={budget_ms}"
        if budget_ms is not None
        else f"latency_ms={latency_ms:.1f}"
    )
    user_payload = {
        "case_id": case_id,
        "expected": expected,
        "actual": compact_for_judge(actual, expected),
        "latency": latency_hint,
        "rubric_axes": list(RUBRIC_AXES),
    }

    client = anthropic.AsyncAnthropic(
        api_key=s.anthropic_api_key.get_secret_value(),
        max_retries=0,
    )
    api_model = resolve_api_model_id(model)
    try:
        response = await client.messages.create(
            model=api_model,
            max_tokens=256,
            system=_JUDGE_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(user_payload, sort_keys=True),
                }
            ],
        )
    except anthropic.NotFoundError as exc:
        raise JudgeScoreError(
            f"judge model {model!r} (api={api_model!r}) not found; "
            f"set ANTHROPIC_MODEL_JUDGE to a model your key can access"
        ) from exc
    except anthropic.APIError as exc:
        raise JudgeScoreError(f"judge Anthropic API error: {exc}") from exc
    finally:
        await client.close()

    text_blocks = [block.text for block in response.content if isinstance(block, TextBlock)]
    if not text_blocks:
        raise JudgeScoreError("judge returned no text blocks")
    raw = _extract_json_object(text_blocks[0])
    scores = JudgeRubricScores.model_validate(raw)
    normalized = scores.normalized()
    input_tokens = int(response.usage.input_tokens)
    output_tokens = int(response.usage.output_tokens)
    try:
        cost_usd = estimate_cost_usd(
            response.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    except UnknownModelPricingError as exc:
        raise JudgeScoreError(str(exc)) from exc

    _log.info(
        "judge.done",
        case_id=case_id,
        model=response.model,
        judge_score=normalized,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        **{axis: getattr(scores, axis) for axis in RUBRIC_AXES},
    )
    return JudgeOutcome(
        score=normalized,
        model=response.model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
    )
