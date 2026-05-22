"""Tests for demo preview helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_financial_data.demo.preview import build_tenk_preview_html


def test_build_tenk_preview_html_injects_props(tmp_path: Path) -> None:
    html_path = build_tenk_preview_html(out_dir=tmp_path)
    html = html_path.read_text(encoding="utf-8")
    assert html_path.is_file()
    assert (tmp_path / "tenk-summary-card.bundle.js").is_file()
    assert "__TENK_UI_PROPS__" in html
    assert "Apple Inc." in html
    assert "item_1a_risk_factors" in html


def test_build_tenk_preview_html_requires_bundle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "mcp_financial_data.demo.preview._bundle_path",
        lambda: tmp_path / "missing.bundle.js",
    )
    with pytest.raises(FileNotFoundError, match="ui-build"):
        build_tenk_preview_html(out_dir=tmp_path)
