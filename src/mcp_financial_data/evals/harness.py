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

import anthropic

from mcp_financial_data import __version__
from mcp_financial_data.evals.dispatch import EvalDispatchError, dispatch_online
from mcp_financial_data.evals.fixtures import get_offline_fixture
from mcp_financial_data.evals.judge import JudgeScoreError, judge_with_claude
from mcp_financial_data.evals.metrics import (
    CaseMetrics,
    citation_coverage,
    exec_accuracy,
    judge_with_stub,
)
from mcp_financial_data.evals.types import EvalCase
from mcp_financial_data.extractors._pricing import UnknownModelPricingError
from mcp_financial_data.extractors.tenk import (
    ExtractorConfigError,
    ExtractorSpendCapError,
    get_total_spend_usd,
)
from mcp_financial_data.logging import configure_logging, get_logger
from mcp_financial_data.settings import Settings, get_settings
from mcp_financial_data.tools.edgar import EdgarConfigError
from mcp_financial_data.tools.fred import FredConfigError
from mcp_financial_data.tools.polygon import PolygonConfigError

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CASES_PATH = REPO_ROOT / "evals" / "cases" / "seed.jsonl"


_ONLINE_CONFIG_ERRORS = (
    EdgarConfigError,
    FredConfigError,
    PolygonConfigError,
    ExtractorConfigError,
)


def _online_config_errors(settings: Settings) -> list[str]:
    """Return human-readable messages for missing live-eval credentials."""
    errors: list[str] = []
    ua = settings.edgar_user_agent.strip()
    if not ua or "@" not in ua:
        errors.append(
            "EDGAR_USER_AGENT must be set to '<Name> <contact@example.com>' "
            "(see .env.example and SEC Fair Access policy)"
        )
    if settings.fred_api_key is None:
        errors.append("FRED_API_KEY is required for fred.* eval cases")
    if settings.anthropic_api_key is None:
        errors.append("ANTHROPIC_API_KEY is required for tenk.extract_section and the live judge")
    return errors


def _validate_online_settings(settings: Settings) -> None:
    """Fail fast before the first live network call when secrets are missing."""
    errors = _online_config_errors(settings)
    if errors:
        msg = "online eval configuration incomplete:\n" + "\n".join(f"  - {e}" for e in errors)
        raise EvalDispatchError(msg)


class EvalBudgetExceededError(Exception):
    """Raised when ``--budget`` is exceeded before the run completes."""


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
    dispatch_cost_usd: float
    judge_cost_usd: float
    input_tokens: int
    output_tokens: int
    judge_input_tokens: int
    judge_output_tokens: int
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
    total_input_tokens: int
    total_output_tokens: int
    total_judge_input_tokens: int
    total_judge_output_tokens: int
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


async def _run_one(
    case: EvalCase,
    *,
    offline: bool,
    settings: Settings,
    budget_usd: float | None,
    spend_so_far_usd: float,
) -> CaseRow:
    """Run one case and return its JSONL row.

    In offline mode, the harness reads a canned fixture from
    ``mcp_financial_data.evals.fixtures``. In online mode, it dispatches to
    the real tool implementations in :mod:`evals.dispatch`.
    """
    log = get_logger("eval").bind(case=case.id, tool=case.tool, offline=offline)
    log.info("case.start")
    t0 = time.perf_counter()

    actual: dict[str, Any] = {}
    error: str | None = None
    dispatch_cost_usd = 0.0
    judge_cost_usd = 0.0
    cost_usd = 0.0
    input_tokens = 0
    output_tokens = 0
    judge_input_tokens = 0
    judge_output_tokens = 0

    try:
        if budget_usd is not None and spend_so_far_usd >= budget_usd:
            raise EvalBudgetExceededError(
                f"--budget {budget_usd:.4f} exceeded (spent={spend_so_far_usd:.4f})"
            )
        if offline or settings.eval_offline:
            actual = get_offline_fixture(case.id)
        else:
            actual, dispatch_cost_usd, input_tokens, output_tokens = await dispatch_online(
                case, settings=settings
            )
            cost_usd = dispatch_cost_usd
            if budget_usd is not None and spend_so_far_usd + cost_usd > budget_usd:
                raise EvalBudgetExceededError(
                    f"--budget {budget_usd:.4f} would be exceeded after dispatch for {case.id}"
                )
    except UnknownModelPricingError as exc:
        error = str(exc)
        log.error("case.pricing_error", err=str(exc))
    except KeyError as exc:
        error = f"missing offline fixture: {exc}"
        log.error("case.fixture_missing", err=str(exc))
    except (EvalDispatchError, TypeError, ValueError, *_ONLINE_CONFIG_ERRORS) as exc:
        error = str(exc)
        log.error("case.dispatch_error", err=str(exc))
    except EvalBudgetExceededError as exc:
        error = str(exc)
        log.error("case.budget_exceeded", err=str(exc))
    except ExtractorSpendCapError as exc:
        error = str(exc)
        log.error("case.spend_cap", err=str(exc))
    except anthropic.APIError as exc:
        error = str(exc)
        log.error("case.api_error", err=str(exc))
    except JudgeScoreError as exc:
        error = str(exc)
        log.error("case.judge_error", err=str(exc))

    success = error is None
    exec_acc = exec_accuracy(case.expected, actual) if success else 0.0
    cit_cov = citation_coverage(actual) if success else 0.0
    latency_ms = (time.perf_counter() - t0) * 1000.0
    if success and (offline or settings.eval_offline):
        judge = judge_with_stub(case.id, exec_acc, cit_cov)
    elif success:
        try:
            outcome = await judge_with_claude(
                case.id,
                case.expected,
                actual,
                model=settings.anthropic_model_judge,
                settings=settings,
                latency_ms=latency_ms,
            )
            judge = outcome.score
            judge_input_tokens = outcome.input_tokens
            judge_output_tokens = outcome.output_tokens
            judge_cost_usd = outcome.cost_usd
            cost_usd = dispatch_cost_usd + judge_cost_usd
            if budget_usd is not None and spend_so_far_usd + cost_usd > budget_usd:
                success = False
                error = (
                    f"--budget {budget_usd:.4f} would be exceeded after judge for {case.id} "
                    f"(spent={spend_so_far_usd:.4f}, case_cost={cost_usd:.4f})"
                )
                log.error("case.budget_exceeded", err=error)
                judge = 0.0
        except JudgeScoreError as exc:
            success = False
            error = str(exc)
            log.error("case.judge_error", err=str(exc))
            judge = 0.0
    else:
        judge = 0.0

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
        dispatch_cost_usd=dispatch_cost_usd,
        judge_cost_usd=judge_cost_usd,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        judge_input_tokens=judge_input_tokens,
        judge_output_tokens=judge_output_tokens,
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
    budget_usd: float | None = None,
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
    spend_usd = get_total_spend_usd()
    for case in cases:
        row = await _run_one(
            case,
            offline=offline,
            settings=settings,
            budget_usd=budget_usd,
            spend_so_far_usd=spend_usd,
        )
        _write_case_row(runs_dir, row)
        rows.append(row)
        spend_usd += row.cost_usd
        if row.error and "budget" in (row.error or "").lower():
            break

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
        total_input_tokens=sum(r.input_tokens for r in rows),
        total_output_tokens=sum(r.output_tokens for r in rows),
        total_judge_input_tokens=sum(r.judge_input_tokens for r in rows),
        total_judge_output_tokens=sum(r.judge_output_tokens for r in rows),
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
    p.add_argument(
        "--budget",
        type=float,
        default=None,
        metavar="USD",
        help="Abort the run when cumulative case cost exceeds this USD cap.",
    )
    p.add_argument(
        "--min-judge-score",
        type=float,
        default=None,
        metavar="SCORE",
        help="Fail the run when mean_judge_score is below this threshold (0.0-1.0).",
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

    online = not args.offline and not settings.eval_offline
    if online:
        try:
            _validate_online_settings(settings)
        except EvalDispatchError as exc:
            sys.stderr.write(f"error: {exc}\n")
            return 2

    summary = asyncio.run(
        run(
            cases_path=args.cases,
            smoke=args.smoke,
            offline=args.offline,
            limit=args.limit,
            settings=settings,
            budget_usd=args.budget,
        )
    )
    if summary.n_pass != summary.n_cases:
        return 1
    if args.min_judge_score is not None and summary.mean_judge_score < args.min_judge_score:
        sys.stderr.write(
            f"error: mean_judge_score {summary.mean_judge_score:.4f} "
            f"< --min-judge-score {args.min_judge_score:.4f}\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
