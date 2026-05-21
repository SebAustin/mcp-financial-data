"""Tests for ``mcp_financial_data.evals.judge``."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from mcp_financial_data.evals.judge import (
    JudgeOutcome,
    JudgeRubricScores,
    JudgeScoreError,
    compact_for_judge,
    judge_with_claude,
)

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"


def test_compact_for_judge_filters_xbrl_facts() -> None:
    actual = {
        "xbrl_facts": [
            {"concept": "Revenues", "fiscal_year": 2025, "value": 1.0},
            {"concept": "Assets", "fiscal_year": 2025, "value": 2.0},
        ]
    }
    expected = {"xbrl_facts": [{"concept": "Revenues", "fiscal_year": 2025}]}
    compact = compact_for_judge(actual, expected)
    assert len(compact["xbrl_facts"]) == 1
    assert compact["xbrl_facts"][0]["concept"] == "Revenues"


def test_judge_rubric_normalized() -> None:
    scores = JudgeRubricScores(
        factual_accuracy=4,
        citation_grounding=5,
        completeness=3,
        format_adherence=5,
        latency_under_budget=2,
    )
    assert scores.normalized() == pytest.approx(3.8 / 5.0)


@pytest.mark.asyncio
@respx.mock
async def test_judge_with_claude_returns_outcome(respx_mock: respx.Router) -> None:
    respx_mock.post(ANTHROPIC_MESSAGES_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "msg_judge",
                "type": "message",
                "role": "assistant",
                "model": "claude-opus-4-7-20260301",
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "factual_accuracy": 5,
                                "citation_grounding": 5,
                                "completeness": 5,
                                "format_adherence": 5,
                                "latency_under_budget": 5,
                            }
                        ),
                    }
                ],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )
    )
    outcome = await judge_with_claude("c1", {"a": 1}, {"a": 1}, model="claude-opus-4-7-20260301")
    assert isinstance(outcome, JudgeOutcome)
    assert outcome.score == 1.0
    assert outcome.input_tokens == 10
    assert outcome.output_tokens == 5
    assert outcome.cost_usd > 0.0


@pytest.mark.asyncio
@respx.mock
async def test_judge_not_found_raises_judge_score_error(respx_mock: respx.Router) -> None:
    respx_mock.post(ANTHROPIC_MESSAGES_URL).mock(
        return_value=httpx.Response(
            404,
            json={
                "type": "error",
                "error": {"type": "not_found_error", "message": "model: bad-model"},
            },
        )
    )
    with pytest.raises(JudgeScoreError, match="not found"):
        await judge_with_claude("c1", {}, {}, model="bad-model")
