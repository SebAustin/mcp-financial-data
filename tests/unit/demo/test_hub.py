"""Tests for demo hub builder."""

from __future__ import annotations

import json
from pathlib import Path

from mcp_financial_data.demo.hub import (
    ANALYST_QUESTION,
    build_demo_hub,
)


def test_build_demo_hub_contains_slides_and_metrics(tmp_path: Path) -> None:
    runs = tmp_path / "evals" / "runs" / "test-run"
    runs.mkdir(parents=True)
    summary = {
        "run_id": "test-run",
        "mean_exec_accuracy": 1.0,
        "mean_citation_coverage": 1.0,
        "mean_judge_score": 1.0,
        "offline": True,
    }
    (runs / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

    hub_dir = tmp_path / "hub"
    index_path = build_demo_hub(out_dir=hub_dir, repo_root=tmp_path, eval_summary=summary)
    html = index_path.read_text(encoding="utf-8")

    assert index_path.name == "index.html"
    assert (hub_dir / "tenk-summary-card.bundle.js").is_file()
    assert ANALYST_QUESTION.split()[0] in html
    assert "__TENK_UI_PROPS__" in html
    assert "Slide 1 — The ask" in html
    assert "exec-accuracy" in html
    assert "test-run" in html
    assert "INFERENCE" in html


def test_build_demo_hub_uses_defaults_without_eval_run(tmp_path: Path) -> None:
    hub_dir = tmp_path / "hub"
    index_path = build_demo_hub(out_dir=hub_dir, repo_root=tmp_path)
    html = index_path.read_text(encoding="utf-8")
    assert index_path.is_file()
    assert "offline-smoke" in html or "offline: true" in html
