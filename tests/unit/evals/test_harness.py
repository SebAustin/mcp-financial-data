"""Tests for ``mcp_financial_data.evals.harness``.

Exercise the offline path end-to-end so the CI smoke step does not regress
silently. Live-network paths are tested in
``tests/unit/evals/test_harness_live.py`` (filled in by W1 follow-up
``prompts/05_evals_full_run.md``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_financial_data.evals import harness
from mcp_financial_data.evals.harness import (
    DEFAULT_CASES_PATH,
    EvalDispatchError,
    _git_sha,
    _load_cases,
    _make_run_id,
    _mean,
    _parser,
    _run_one,
    main,
    run,
)
from mcp_financial_data.evals.types import EvalCase
from mcp_financial_data.settings import reload_settings


def test_default_cases_path_exists() -> None:
    assert DEFAULT_CASES_PATH.exists(), DEFAULT_CASES_PATH


def test_load_cases_reads_seed_jsonl() -> None:
    cases = _load_cases(DEFAULT_CASES_PATH)
    assert len(cases) == 5
    assert all(isinstance(c, EvalCase) for c in cases)
    assert {c.id for c in cases} == {
        "edgar-aapl-list-10k-2025",
        "edgar-msft-revenues-fy2025",
        "edgar-googl-list-8k-2025",
        "fred-gdp-q1-2025",
        "tenk-aapl-risk-factors",
    }


def test_load_cases_skips_blank_and_comment_lines(tmp_path: Path) -> None:
    p = tmp_path / "cases.jsonl"
    p.write_text(
        "\n"
        "// a comment\n"
        '{"id": "x", "tool": "edgar.list_filings", "description": "d", '
        '"input": {}, "expected": {}}\n'
        "\n",
        encoding="utf-8",
    )
    cases = _load_cases(p)
    assert len(cases) == 1
    assert cases[0].id == "x"


def test_make_run_id_format() -> None:
    rid = _make_run_id()
    assert "_" in rid
    stamp, sha = rid.split("_", 1)
    assert len(stamp) == 16
    assert sha != ""


def test_git_sha_is_string() -> None:
    sha = _git_sha()
    assert isinstance(sha, str)
    assert sha != ""


def test_mean_zero_on_empty() -> None:
    assert _mean([]) == 0.0
    assert _mean([1.0, 2.0, 3.0]) == 2.0


@pytest.mark.asyncio
async def test_run_one_offline_happy_path() -> None:
    settings = reload_settings()
    case = EvalCase(
        id="edgar-aapl-list-10k-2025",
        tool="edgar.list_filings",
        description="smoke",
        input={"cik": "0000320193", "form": "10-K", "limit": 1},
        expected={
            "filings": [
                {
                    "cik": "0000320193",
                    "accession_number": "0000320193-25-000079",
                    "form": "10-K",
                    "filing_date": "2025-10-31",
                    "primary_document": "aapl-20250927.htm",
                }
            ]
        },
    )
    row = await _run_one(
        case, offline=True, settings=settings, budget_usd=None, spend_so_far_usd=0.0
    )
    assert row.success is True
    assert row.exec_accuracy == 1.0
    assert row.citation_coverage == 1.0
    assert row.error is None


@pytest.mark.asyncio
async def test_run_one_offline_fixture_missing() -> None:
    settings = reload_settings()
    case = EvalCase(
        id="not-in-fixtures",
        tool="edgar.list_filings",
        description="missing",
        input={},
        expected={},
    )
    row = await _run_one(
        case, offline=True, settings=settings, budget_usd=None, spend_so_far_usd=0.0
    )
    assert row.success is False
    assert row.exec_accuracy == 0.0
    assert "missing offline fixture" in (row.error or "")


@pytest.mark.asyncio
async def test_run_one_online_requires_dispatch_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVAL_OFFLINE", "0")
    settings = reload_settings()
    case = EvalCase(
        id="edgar-aapl-list-10k-2025",
        tool="edgar.list_filings",
        description="online",
        input={},
        expected={},
    )
    row = await _run_one(
        case,
        offline=False,
        settings=settings,
        budget_usd=None,
        spend_so_far_usd=0.0,
    )
    assert row.success is False
    assert row.error is not None


@pytest.mark.asyncio
async def test_run_writes_summary_and_per_case_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(harness, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("EVAL_RUNS_DIR", "runs")
    settings = reload_settings()
    cases_path = tmp_path / "seed.jsonl"
    cases_path.write_text(DEFAULT_CASES_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    summary = await run(
        cases_path=cases_path,
        smoke=True,
        offline=True,
        limit=None,
        settings=settings,
    )
    assert summary.n_cases == 1
    assert summary.n_pass == 1
    runs_root = tmp_path / "runs" / summary.run_id
    assert (runs_root / "summary.json").exists()
    assert (runs_root / "summary.jsonl").exists()
    summary_data = json.loads((runs_root / "summary.json").read_text(encoding="utf-8"))
    assert summary_data["n_pass"] == 1
    assert summary_data["mean_judge_score"] == 1.0
    assert summary_data["total_judge_input_tokens"] == 0


def test_parser_requires_one_of_smoke_full_limit() -> None:
    # ``main([])`` writes to stderr and returns 2; we don't call asyncio.run
    # here because the no-arg branch short-circuits before that.
    rc = main([])
    assert rc == 2


def test_parser_accepts_smoke_offline() -> None:
    p = _parser()
    args = p.parse_args(["--smoke", "--offline"])
    assert args.smoke is True
    assert args.offline is True
    assert args.full is False


def test_parser_accepts_budget_and_min_judge_score() -> None:
    p = _parser()
    args = p.parse_args(["--full", "--budget", "2.50", "--min-judge-score", "0.85"])
    assert args.budget == pytest.approx(2.50)
    assert args.min_judge_score == pytest.approx(0.85)


def test_main_fails_when_online_config_incomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVAL_OFFLINE", "0")

    def _fail_validation(_settings: object) -> None:
        raise EvalDispatchError("online eval configuration incomplete")

    monkeypatch.setattr(harness, "_validate_online_settings", _fail_validation)
    reload_settings()
    rc = main(["--full"])
    assert rc == 2


def test_main_fails_when_min_judge_score_not_met(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(harness, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("EVAL_RUNS_DIR", "runs")
    cases_path = tmp_path / "seed.jsonl"
    cases_path.write_text(DEFAULT_CASES_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(
        harness,
        "DEFAULT_CASES_PATH",
        cases_path,
    )
    rc = main(["--smoke", "--offline", "--min-judge-score", "1.01", "--cases", str(cases_path)])
    assert rc == 1


# ``main(...)`` with --smoke is exercised end-to-end through the
# ``run()`` direct call in ``test_run_writes_summary_and_per_case_jsonl``;
# we deliberately skip an additional CLI-driven test here because it would
# spin up FastMCP's transport (sockets + event loop) only to tear it down,
# producing pytest unraisable-exception warnings that flake CI.
