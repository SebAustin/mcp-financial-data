"""Eval harness for mcp-financial-data.

Smoke: ``uv run python -m mcp_financial_data.evals.harness --smoke --offline``

Output:
- ``evals/runs/<run_id>/<case_id>.jsonl``: per-case rows (one per case).
- ``evals/runs/<run_id>/summary.jsonl``: one summary row at the end.
- ``evals/runs/<run_id>/summary.json``: machine-readable rollup for CI deltas.

Run id format: ``<UTC ISO date>_<short git SHA or 'nogit'>``.

Contract:
- Every metric is numeric.
- LLM-as-judge is paired with deterministic ``exec_accuracy`` and
  ``citation_coverage``.
- ``--offline`` short-circuits any external call. The CI smoke slice always
  uses ``--offline``.
- The ``MAX_API_SPEND_USD`` cap is enforced before any non-offline call.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import random
import shutil
import subprocess
import sys
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mcp_financial_data import __version__
from mcp_financial_data.evals.fixtures import get_offline_fixture
from mcp_financial_data.evals.metrics import (
    CaseMetrics,
    citation_coverage,
    exec_accuracy,
    judge_with_stub,
)
from mcp_financial_data.logging import configure_logging, get_logger
from mcp_financial_data.settings import Settings, get_settings

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CASES_PATH = REPO_ROOT / "evals" / "cases" / "seed.jsonl"


@dataclass(frozen=True, slots=True)
class EvalCase:
    """One row from the seed JSONL set."""

    id: str
    tool: str
    description: str
    input: dict[str, Any]
    expected: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CaseRow:
    """One JSONL row written for a single eval case."""

    id: str
    tool: str
    description: str
    success: bool
    exec_accuracy: float
    citation_coverage: float
    judge_score: float
    latency_ms: float
    cost_usd: float
    error: str | None
    actual: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RunSummary:
    """Final summary row written at the end of the run."""

    run_id: str
    started_at: str
    finished_at: str
    duration_ms: float
    git_sha: str
    harness_version: str
    model_primary: str
    model_judge: str
    offline: bool
    n_cases: int
    n_pass: int
    mean_exec_accuracy: float
    mean_citation_coverage: float
    mean_judge_score: float
    mean_latency_ms: float
    total_cost_usd: float
    host: dict[str, str]
    cases: list[str]


def _git_sha() -> str:
    """Return the short HEAD SHA, or ``'nogit'`` if not a git repo yet."""
    git = shutil.which("git")
    if git is None:
        return "nogit"
    try:
        out = subprocess.check_output(  # noqa: S603 — argv resolved via shutil.which
            [git, "rev-parse", "--short", "HEAD"],
            cwd=str(REPO_ROOT),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out or "nogit"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "nogit"


def _make_run_id() -> str:
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}_{_git_sha()}"


def _load_cases(path: Path) -> list[EvalCase]:
    """Parse a JSONL file of eval cases."""
    cases: list[EvalCase] = []
    with path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("//"):
                continue
            data = json.loads(line)
            cases.append(EvalCase(**data))
    return cases


async def _run_one(case: EvalCase, *, offline: bool, settings: Settings) -> CaseRow:
    """Run one case and return its JSONL row.

    In offline mode, the harness reads a canned fixture from
    ``mcp_financial_data.evals.fixtures``. In online mode, it would dispatch
    to the real tool (filled in by ``prompts/05_evals_full_run.md``).
    """
    log = get_logger("eval").bind(case=case.id, tool=case.tool, offline=offline)
    log.info("case.start")
    t0 = time.perf_counter()

    actual: dict[str, Any] = {}
    error: str | None = None
    cost_usd = 0.0

    try:
        if offline or settings.eval_offline:
            actual = get_offline_fixture(case.id)
        else:
            error = "online mode not yet implemented; see prompts/05_evals_full_run.md"
            log.warning("case.online_not_implemented")
    except KeyError as exc:
        error = f"missing offline fixture: {exc}"
        log.error("case.fixture_missing", err=str(exc))

    success = error is None
    exec_acc = exec_accuracy(case.expected, actual) if success else 0.0
    cit_cov = citation_coverage(actual) if success else 0.0
    judge = judge_with_stub(case.id, exec_acc, cit_cov) if success else 0.0
    latency_ms = (time.perf_counter() - t0) * 1000.0

    metrics = CaseMetrics(
        exec_accuracy=exec_acc,
        citation_coverage=cit_cov,
        judge_score=judge,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        success=success,
    )
    log.info("case.done", **asdict(metrics))

    return CaseRow(
        id=case.id,
        tool=case.tool,
        description=case.description,
        success=success,
        exec_accuracy=exec_acc,
        citation_coverage=cit_cov,
        judge_score=judge,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        error=error,
        actual=actual,
    )


def _write_summary(run_dir: Path, summary: RunSummary) -> None:
    summary_jsonl = run_dir / "summary.jsonl"
    with summary_jsonl.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(summary), sort_keys=True) + "\n")
    summary_json = run_dir / "summary.json"
    summary_json.write_text(
        json.dumps(asdict(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_case_row(run_dir: Path, row: CaseRow) -> None:
    out = run_dir / f"{row.id}.jsonl"
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(row), sort_keys=True) + "\n")


async def run(
    *,
    cases_path: Path,
    smoke: bool,
    offline: bool,
    limit: int | None,
    settings: Settings,
) -> RunSummary:
    """Run the eval suite. Returns the summary row that was just written."""
    log = get_logger("eval")
    cases = _load_cases(cases_path)
    if limit is not None:
        cases = cases[:limit]
    if smoke:
        cases = cases[:1]

    run_id = _make_run_id()
    runs_dir = REPO_ROOT / settings.eval_runs_dir / run_id
    runs_dir.mkdir(parents=True, exist_ok=True)
    log.info("run.start", run_id=run_id, n_cases=len(cases), offline=offline)
    started_at = datetime.now(tz=UTC).isoformat()
    t0 = time.perf_counter()

    rows: list[CaseRow] = []
    for case in cases:
        row = await _run_one(case, offline=offline, settings=settings)
        _write_case_row(runs_dir, row)
        rows.append(row)

    duration_ms = (time.perf_counter() - t0) * 1000.0
    n_pass = sum(1 for r in rows if r.success)
    summary = RunSummary(
        run_id=run_id,
        started_at=started_at,
        finished_at=datetime.now(tz=UTC).isoformat(),
        duration_ms=duration_ms,
        git_sha=_git_sha(),
        harness_version=__version__,
        model_primary=settings.anthropic_model_primary,
        model_judge=settings.anthropic_model_judge,
        offline=offline or settings.eval_offline,
        n_cases=len(rows),
        n_pass=n_pass,
        mean_exec_accuracy=_mean(r.exec_accuracy for r in rows),
        mean_citation_coverage=_mean(r.citation_coverage for r in rows),
        mean_judge_score=_mean(r.judge_score for r in rows),
        mean_latency_ms=_mean(r.latency_ms for r in rows),
        total_cost_usd=sum(r.cost_usd for r in rows),
        host={
            "python": platform.python_version(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        cases=[r.id for r in rows],
    )
    _write_summary(runs_dir, summary)
    log.info(
        "run.done",
        run_id=run_id,
        n_cases=summary.n_cases,
        n_pass=summary.n_pass,
        mean_judge_score=summary.mean_judge_score,
    )
    return summary


def _mean(values: Iterable[float]) -> float:
    """Mean of a finite iterable of floats; 0.0 when empty."""
    items = list(values)
    if not items:
        return 0.0
    return float(sum(items)) / len(items)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mcp_financial_data.evals.harness")
    p.add_argument("--smoke", action="store_true", help="Run only the first case.")
    p.add_argument("--full", action="store_true", help="Run every case in the seed set.")
    p.add_argument("--limit", type=int, default=None, help="Cap the number of cases to run.")
    p.add_argument(
        "--offline",
        action="store_true",
        help="Use canned fixtures and the deterministic stub judge. CI default.",
    )
    p.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES_PATH,
        help=f"Path to the JSONL cases file. Default: {DEFAULT_CASES_PATH}",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint. Returns process exit code (0 on success)."""
    args = _parser().parse_args(argv)
    if not (args.smoke or args.full or args.limit is not None):
        sys.stderr.write("error: pass one of --smoke / --full / --limit N\n")
        return 2

    configure_logging()
    settings = get_settings()
    random.seed(settings.eval_seed)
    os.environ.setdefault("PYTHONHASHSEED", "0")

    summary = asyncio.run(
        run(
            cases_path=args.cases,
            smoke=args.smoke,
            offline=args.offline,
            limit=args.limit,
            settings=settings,
        )
    )
    return 0 if summary.n_pass == summary.n_cases else 1


if __name__ == "__main__":
    raise SystemExit(main())
