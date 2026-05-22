"""Build a browser-openable TenKSummaryCard preview from offline fixtures."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Final

from mcp_financial_data.apps.ui import (
    TenKSummaryCardProps,
    _bundle_path,
    _html_path,
    render_tenk_summary_card,
)
from mcp_financial_data.evals.fixtures import get_offline_fixture
from mcp_financial_data.extractors.tenk import ExtractionResult

DEFAULT_PREVIEW_DIR: Final[Path] = Path("recordings/demo-preview")
PREVIEW_HTML_NAME: Final[str] = "tenk-summary-card.html"
PREVIEW_BUNDLE_NAME: Final[str] = "tenk-summary-card.bundle.js"


def default_preview_dir() -> Path:
    """Return the gitignored directory used for local demo recordings."""
    return DEFAULT_PREVIEW_DIR


def build_tenk_preview_html(
    *,
    out_dir: Path | None = None,
    cik: str = "0000320193",
    company_name: str = "Apple Inc.",
) -> Path:
    """Write a self-contained HTML preview and return its path.

    Copies the shipped JS bundle beside the HTML shell and injects
    ``window.__TENK_UI_PROPS__`` so the card renders without an MCP host.
    """
    target_dir = (out_dir or default_preview_dir()).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    extraction = ExtractionResult.model_validate(get_offline_fixture("tenk-aapl-risk-factors"))
    envelope = render_tenk_summary_card(
        TenKSummaryCardProps(
            extraction=extraction,
            cik=cik,
            company_name=company_name,
        )
    )

    bundle_src = _bundle_path()
    if not bundle_src.is_file():
        msg = f"MCP Apps bundle missing at {bundle_src}; run `make ui-build`."
        raise FileNotFoundError(msg)

    bundle_dst = target_dir / PREVIEW_BUNDLE_NAME
    shutil.copy2(bundle_src, bundle_dst)

    shell = _html_path().read_text(encoding="utf-8")
    props_json = json.dumps(envelope, separators=(",", ":"))
    injected = shell.replace(
        '<script src="./tenk-summary-card.bundle.js"></script>',
        (
            f"<script>window.__TENK_UI_PROPS__ = {props_json};</script>\n"
            f'    <script src="./{PREVIEW_BUNDLE_NAME}"></script>'
        ),
    )

    html_path = target_dir / PREVIEW_HTML_NAME
    html_path.write_text(injected, encoding="utf-8")
    return html_path
