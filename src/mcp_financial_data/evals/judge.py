"""LLM-as-judge for the eval harness (Claude Opus 4.7).

Paired with deterministic metrics per master rules §5. The rubric scores five
axes on a 0-5 scale; the harness stores ``judge_score = mean_axis / 5.0``.

See ``docs/adr/0009-llm-judge-rubric-and-replayability.md``.
"""

from __future__ import annotations

import json
import re
from typing import Any, Final

import anthropic
from anthropic.types import TextBlock
from pydantic import BaseModel, ConfigDict, Field

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

_JUDGE_SYSTEM: Final[str] = (
    "You are an eval judge for a financial MCP server. Score the ACTUAL tool "
    "output against EXPECTED reference data on five axes from 0 to 5 "
    "(integers only). Return ONLY a JSON object with those five keys and "
    "integer values. No prose."
)


class JudgeScoreError(Exception):
    """Raised when the judge model returns an unparseable response."""


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
) -> float:
    """LLM-as-judge call against Claude. Returns a score in [0.0, 1.0].

    Args:
        case_id: Eval case identifier (logged only).
        expected: Reference output from the seed JSONL row.
        actual: Tool output produced by online or offline dispatch.
        model: Judge model id (typically Opus 4.7).
        settings: Optional settings override.
        latency_ms: Wall-clock latency for the case (feeds ``latency_under_budget``).
        budget_ms: Optional per-case latency budget in milliseconds.
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
        "actual": actual,
        "latency": latency_hint,
        "rubric_axes": list(RUBRIC_AXES),
    }

    client = anthropic.AsyncAnthropic(
        api_key=s.anthropic_api_key.get_secret_value(),
        max_retries=0,
    )
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=256,
            system=_JUDGE_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(user_payload, sort_keys=True),
                }
            ],
        )
    finally:
        await client.close()

    text_blocks = [block.text for block in response.content if isinstance(block, TextBlock)]
    if not text_blocks:
        raise JudgeScoreError("judge returned no text blocks")
    raw = _extract_json_object(text_blocks[0])
    scores = JudgeRubricScores.model_validate(raw)
    normalized = scores.normalized()
    _log.info(
        "judge.done",
        case_id=case_id,
        model=response.model,
        judge_score=normalized,
        **{axis: getattr(scores, axis) for axis in RUBRIC_AXES},
    )
    return normalized
