"""Tests for ``mcp_financial_data.evals.metrics``."""

from __future__ import annotations

import pytest

from mcp_financial_data.evals.metrics import (
    citation_coverage,
    exec_accuracy,
    judge_with_claude,
    judge_with_stub,
)


def test_exec_accuracy_perfect() -> None:
    assert exec_accuracy({"a": 1, "b": 2}, {"a": 1, "b": 2}) == 1.0


def test_exec_accuracy_partial() -> None:
    assert exec_accuracy({"a": 1, "b": 2}, {"a": 1, "b": 99}) == 0.5


def test_exec_accuracy_missing_key() -> None:
    assert exec_accuracy({"a": 1, "b": 2}, {"a": 1}) == 0.5


def test_exec_accuracy_empty_expected_is_one() -> None:
    assert exec_accuracy({}, {"x": 1}) == 1.0


def test_citation_coverage_non_extractor_is_one() -> None:
    assert citation_coverage({"filings": [{"cik": "1", "form": "10-K"}]}) == 1.0
    assert citation_coverage({"xbrl_facts": [{"concept": "Revenues"}]}) == 1.0


def test_citation_coverage_extractor_full() -> None:
    actual = {
        "model": "claude-sonnet-4-5-20260301",
        "facts": [
            {"text": "fact 1", "citations": [{"document_title": "x"}]},
            {"text": "fact 2", "citations": [{"document_title": "y"}]},
        ],
    }
    assert citation_coverage(actual) == 1.0


def test_citation_coverage_extractor_partial() -> None:
    actual = {
        "model": "claude-sonnet-4-5-20260301",
        "facts": [
            {"text": "fact 1", "citations": [{"document_title": "x"}]},
            {"text": "fact 2", "citations": []},
        ],
    }
    assert citation_coverage(actual) == 0.5


def test_judge_with_stub_is_pure() -> None:
    a = judge_with_stub("c1", 1.0, 1.0)
    b = judge_with_stub("c1", 1.0, 1.0)
    assert a == b == 1.0
    assert judge_with_stub("c2", 0.5, 0.5) == 0.5


@pytest.mark.asyncio
async def test_judge_with_claude_is_stub() -> None:
    with pytest.raises(NotImplementedError, match=r"prompts/05_evals_full_run\.md"):
        await judge_with_claude("c1", {}, {}, model="claude-opus-4-7-20260301")
