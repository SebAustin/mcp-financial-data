"""MCP Apps inline UI registration.

Per MCP spec 2025-11-25 / SEP-1865, servers associate predeclared ``ui://``
resources with tools via ``_meta.ui.resourceUri``. This module builds the
server-side **UI envelope** that accompanies ``tenk.extract_section`` results:
typed props, citation pills with SEC EDGAR browse URLs, and a content-addressed
reference to the React bundle shipped under ``static/ui/``.

See ``docs/adr/0008-mcp-apps-bundle-distribution.md``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from mcp_financial_data.extractors.tenk import ExtractionResult

TENK_SUMMARY_CARD_ID: Final[str] = "tenk-summary-card"
RESOURCE_MIME_TYPE: Final[str] = "text/html;profile=mcp-app"
SERVER_UI_SCHEME: Final[str] = "ui://mcp-financial-data"
TENK_SUMMARY_CARD_RESOURCE_URI: Final[str] = f"{SERVER_UI_SCHEME}/{TENK_SUMMARY_CARD_ID}"

#: Wheel-relative path baked by hatch ``force-include`` (ADR 0008).
BUNDLE_RELATIVE_PATH: Final[str] = "static/ui/tenk-summary-card.bundle.js"
HTML_RELATIVE_PATH: Final[str] = "static/ui/tenk-summary-card.html"

REPO_ROOT = Path(__file__).resolve().parents[3]
_PKG_STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "ui"
_PKG_STATIC_BUNDLE = _PKG_STATIC_DIR / "tenk-summary-card.bundle.js"
_PKG_STATIC_HTML = _PKG_STATIC_DIR / "tenk-summary-card.html"


def _bundle_path() -> Path:
    """Resolve the bundle on disk for dev checkouts and installed wheels."""
    if _PKG_STATIC_BUNDLE.is_file():
        return _PKG_STATIC_BUNDLE
    return REPO_ROOT / BUNDLE_RELATIVE_PATH


class TenKSummaryCardProps(BaseModel):
    """Props consumed by the TenKSummaryCard React component."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    extraction: ExtractionResult
    cik: str = Field(..., min_length=1, max_length=10)
    company_name: str = Field(..., min_length=1)


class UiBundleReference(BaseModel):
    """Content-addressed pointer to the shipped JS bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(..., min_length=1, description="Path relative to package root.")
    sha256: str = Field(..., min_length=64, max_length=64)
    uri: str = Field(..., min_length=1)


class CitationPill(BaseModel):
    """One clickable citation pill in the inline card."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_text: str = Field(..., min_length=1)
    document_title: str = Field(..., min_length=1)
    cited_text: str = Field(..., min_length=1)
    start_char_index: int = Field(..., ge=0)
    end_char_index: int = Field(..., ge=0)
    url: str = Field(..., min_length=1)


class McpUiEnvelope(BaseModel):
    """JSON-serializable MCP Apps UI envelope for tool results."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["ui"] = "ui"
    id: str
    component: str
    resourceUri: str
    mimeType: str = RESOURCE_MIME_TYPE
    props: dict[str, Any]
    bundle: UiBundleReference
    citationPills: tuple[CitationPill, ...] = ()


def sec_edgar_browse_url(cik: str, *, form: str = "10-K") -> str:
    """Build the SEC EDGAR company browse URL used by citation pills.

    Uses the ``cgi-bin/browse-edgar`` pattern required by prompt 04 acceptance.
    """
    cik_num = str(int(cik.strip().lstrip("0") or "0"))
    return (
        "https://www.sec.gov/cgi-bin/browse-edgar"
        f"?action=getcompany&CIK={cik_num}&type={form}&dateb=&owner=include&count=40"
    )


def bundle_sha256(path: Path | None = None) -> str:
    """Return the lowercase hex SHA-256 digest of the on-disk bundle."""
    target = path or _bundle_path()
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return digest


def _citation_pills(extraction: ExtractionResult, *, cik: str) -> tuple[CitationPill, ...]:
    """Flatten ``CitedClaim`` citations into UI pills with SEC browse URLs."""
    browse = sec_edgar_browse_url(cik)
    pills: list[CitationPill] = []
    for claim in extraction.facts:
        for citation in claim.citations:
            pills.append(
                CitationPill(
                    claim_text=claim.text,
                    document_title=citation.document_title,
                    cited_text=citation.cited_text,
                    start_char_index=citation.start_char_index,
                    end_char_index=citation.end_char_index,
                    url=browse,
                )
            )
    return tuple(pills)


def render_tenk_summary_card(props: TenKSummaryCardProps) -> dict[str, object]:
    """Build the MCP Apps UI message for the TenKSummaryCard.

    Returns a JSON-serializable dict validating as :class:`McpUiEnvelope`.
    The bundle hash is computed from the file on disk so CI can detect drift
    between source and shipped artifact.
    """
    bundle_path = _bundle_path()
    if not bundle_path.is_file():
        msg = f"MCP Apps bundle missing at {bundle_path}; run `make ui-build` from the repo root."
        raise FileNotFoundError(msg)

    envelope = McpUiEnvelope(
        id=TENK_SUMMARY_CARD_ID,
        component=TENK_SUMMARY_CARD_ID,
        resourceUri=TENK_SUMMARY_CARD_RESOURCE_URI,
        mimeType=RESOURCE_MIME_TYPE,
        props=props.model_dump(mode="json"),
        bundle=UiBundleReference(
            path=BUNDLE_RELATIVE_PATH,
            sha256=bundle_sha256(),
            uri=TENK_SUMMARY_CARD_RESOURCE_URI,
        ),
        citationPills=_citation_pills(props.extraction, cik=props.cik),
    )
    return envelope.model_dump(mode="json")


def _html_path() -> Path:
    """Resolve the MCP Apps HTML shell for dev checkouts and installed wheels."""
    if _PKG_STATIC_HTML.is_file():
        return _PKG_STATIC_HTML
    return REPO_ROOT / HTML_RELATIVE_PATH


def read_bundle_bytes() -> bytes:
    """Return the shipped JS bundle bytes for ``resources/read`` handlers."""
    return _bundle_path().read_bytes()


def read_resource_html() -> str:
    """Return the HTML shell that loads the TenKSummaryCard bundle."""
    path = _html_path()
    if not path.is_file():
        msg = f"MCP Apps HTML missing at {path}; run `make ui-build` from the repo root."
        raise FileNotFoundError(msg)
    return path.read_text(encoding="utf-8")
