"""Post the latest eval summary as a sticky PR comment.

Reads ``evals/runs/<latest>/summary.json``, formats it as a markdown table,
and posts (or replaces) the sticky ``mcp-financial-data eval delta`` comment
on the open PR via the ``gh`` CLI. Designed to no-op gracefully if no run
exists for the current SHA so a CI step that's still running doesn't fail.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = REPO_ROOT / "evals" / "runs"
STICKY_HEADER = "<!-- mcp-financial-data:eval-delta -->"


def _latest_summary() -> Path | None:
    if not RUNS_DIR.exists():
        return None
    candidates = [d / "summary.json" for d in RUNS_DIR.iterdir() if d.is_dir()]
    candidates = [p for p in candidates if p.exists()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _format(summary: dict[str, object]) -> str:
    rows = [
        ("run_id", summary.get("run_id")),
        ("git_sha", summary.get("git_sha")),
        ("offline", summary.get("offline")),
        ("n_cases", summary.get("n_cases")),
        ("n_pass", summary.get("n_pass")),
        ("mean_exec_accuracy", summary.get("mean_exec_accuracy")),
        ("mean_citation_coverage", summary.get("mean_citation_coverage")),
        ("mean_judge_score", summary.get("mean_judge_score")),
        ("mean_latency_ms", summary.get("mean_latency_ms")),
        ("total_cost_usd", summary.get("total_cost_usd")),
    ]
    body_lines = [
        STICKY_HEADER,
        "## eval delta — mcp-financial-data",
        "",
        "| metric | value |",
        "| --- | --- |",
        *[f"| `{k}` | `{v}` |" for k, v in rows],
    ]
    return "\n".join(body_lines)


def _post_comment(body: str) -> int:
    pr_number = os.environ.get("PR_NUMBER") or _detect_pr_number()
    if not pr_number:
        sys.stderr.write("post_eval_delta: no PR number in env or context; skipping\n")
        return 0
    gh = shutil.which("gh")
    if gh is None:
        sys.stderr.write("post_eval_delta: `gh` CLI not on PATH; skipping comment\n")
        return 0
    proc = subprocess.run(  # noqa: S603 — argv resolved via shutil.which
        [gh, "pr", "comment", pr_number, "--edit-last", "--body", body],
        check=False,
    )
    if proc.returncode != 0:
        proc = subprocess.run(  # noqa: S603 — argv resolved via shutil.which
            [gh, "pr", "comment", pr_number, "--body", body],
            check=False,
        )
    return proc.returncode


def _detect_pr_number() -> str | None:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        return None
    p = Path(event_path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    pr = data.get("pull_request") or data.get("issue")
    if not isinstance(pr, dict):
        return None
    n = pr.get("number")
    return str(n) if n else None


def main() -> int:
    summary_path = _latest_summary()
    if summary_path is None:
        sys.stderr.write("post_eval_delta: no summary.json found; nothing to post\n")
        return 0
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    body = _format(summary)
    return _post_comment(body)


if __name__ == "__main__":
    raise SystemExit(main())
