"""respx-mocked end-to-end tests for the eval harness online dispatch path."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from mcp_financial_data.evals.harness import _run_one
from mcp_financial_data.evals.types import EvalCase
from mcp_financial_data.extractors.tenk import reset_spend_counter
from mcp_financial_data.settings import Settings, reload_settings
from mcp_financial_data.tools import edgar as edgar_mod
from mcp_financial_data.tools.cache import SqliteCache

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
EDGAR_SUBMISSIONS = "https://data.sec.gov/submissions/CIK0000320193.json"


@pytest.fixture(autouse=True)
def _reset_extractor_spend() -> None:
    reset_spend_counter()


@pytest.fixture
def online_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    """Force online dispatch: no offline fixtures, fresh EDGAR cache."""
    monkeypatch.setenv("EVAL_OFFLINE", "false")
    monkeypatch.setenv("EDGAR_USER_AGENT", "Test Bot <test@example.com>")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    store = SqliteCache(path=tmp_path / "eval_edgar_cache.sqlite")
    monkeypatch.setattr(edgar_mod, "_DEFAULT_CACHE", store, raising=False)
    return reload_settings()


def _judge_payload() -> dict[str, object]:
    return {
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
        "stop_sequence": None,
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }


@pytest.mark.asyncio
@respx.mock(assert_all_called=True)
async def test_run_one_online_edgar_list_filings(
    respx_mock: respx.Router, online_settings: Settings
) -> None:
    settings = online_settings
    respx_mock.get(EDGAR_SUBMISSIONS).mock(
        return_value=httpx.Response(
            200,
            json={
                "filings": {
                    "recent": {
                        "accessionNumber": ["0000320193-25-000001"],
                        "filingDate": ["2025-11-01"],
                        "form": ["10-K"],
                        "primaryDocument": ["aapl-10k.htm"],
                        "primaryDocDescription": [""],
                    }
                }
            },
        )
    )
    respx_mock.post(ANTHROPIC_MESSAGES_URL).mock(
        return_value=httpx.Response(200, json=_judge_payload())
    )

    case = EvalCase(
        id="edgar-aapl-list-10k-2025",
        tool="edgar.list_filings",
        description="online edgar",
        input={"cik": "0000320193", "form": "10-K", "limit": 1},
        expected={
            "filings": [
                {
                    "cik": "0000320193",
                    "accession_number": "0000320193-25-000001",
                    "form": "10-K",
                    "filing_date": "2025-11-01",
                    "primary_document": "aapl-10k.htm",
                }
            ]
        },
    )
    row = await _run_one(
        case,
        offline=False,
        settings=settings,
        budget_usd=None,
        spend_so_far_usd=0.0,
    )
    assert row.success is True
    assert row.exec_accuracy == 1.0
    assert row.judge_score == 1.0
    assert row.actual["filings"][0]["form"] == "10-K"


@pytest.mark.asyncio
@respx.mock(assert_all_called=True)
async def test_run_one_budget_abort_before_dispatch(respx_mock: respx.Router) -> None:
    settings = reload_settings()
    case = EvalCase(
        id="edgar-aapl-list-10k-2025",
        tool="edgar.list_filings",
        description="budget",
        input={"cik": "0000320193", "form": "10-K", "limit": 1},
        expected={"filings": []},
    )
    row = await _run_one(
        case,
        offline=False,
        settings=settings,
        budget_usd=0.0,
        spend_so_far_usd=0.0,
    )
    assert row.success is False
    assert "budget" in (row.error or "").lower()
    assert respx_mock.calls.call_count == 0
