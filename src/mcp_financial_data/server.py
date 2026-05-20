"""FastMCP server entry point.

Builds the streamable-HTTP MCP server, registers all tools, and binds the
MCP Apps UI components. Real OAuth + EDGAR + Anthropic wiring lands in the
W1 Cursor prompt pack — the scaffold below is structurally complete and
typecheck-clean.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Final

from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from mcp_financial_data import __version__
from mcp_financial_data.apps.ui import (
    TENK_SUMMARY_CARD_RESOURCE_URI,
    TenKSummaryCardProps,
    render_tenk_summary_card,
)
from mcp_financial_data.extractors.tenk import (
    ExtractionResult,
    TenKSection,
    extract_tenk_section,
)
from mcp_financial_data.logging import configure_logging, get_logger
from mcp_financial_data.settings import Settings, get_settings
from mcp_financial_data.tools.edgar import (
    EdgarFact,
    EdgarFiling,
    fetch_company_facts,
    list_filings,
)
from mcp_financial_data.tools.fred import FredSeries, fetch_series
from mcp_financial_data.tools.polygon import (
    PolygonAggregateBar,
    Timespan,
    fetch_aggregates,
)

SERVER_NAME: Final[str] = "mcp-financial-data"


class ListFilingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cik: str = Field(..., min_length=1, max_length=10)
    form: str | None = None
    limit: int = Field(default=40, ge=1, le=1000)


class CompanyFactsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cik: str = Field(..., min_length=1, max_length=10)


class FredSeriesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_id: str = Field(..., min_length=1, max_length=64)
    start: date | None = None
    end: date | None = None


class PolygonAggregatesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(..., min_length=1, max_length=12)
    multiplier: int = Field(..., ge=1, le=1000)
    timespan: Timespan
    start: date
    end: date
    adjusted: bool = True
    limit: int = Field(default=5000, ge=1, le=50000)


class ExtractTenKInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section: TenKSection
    cik: str = Field(..., min_length=1, max_length=10, description="Issuer CIK, e.g. 0000320193.")
    company_name: str = Field(..., min_length=1, description="Display name, e.g. Apple Inc.")


class TenKExtractOutput(BaseModel):
    """Extractor result plus the MCP Apps inline UI envelope."""

    model_config = ConfigDict(extra="forbid")

    extraction: ExtractionResult
    ui: dict[str, object] = Field(
        ...,
        description="MCP Apps UI envelope (see apps.ui.McpUiEnvelope).",
    )


def build_app(settings: Settings | None = None) -> FastMCP[Any]:
    """Build and return the FastMCP application with all tools registered.

    No network is touched here — this is what CI calls in its smoke check.
    """
    s = settings or get_settings()
    log = get_logger("server").bind(version=__version__, audience=s.mcp_oauth_audience)
    log.info("server.build_start")

    mcp: FastMCP[Any] = FastMCP(
        name=SERVER_NAME,
        instructions=(
            "Read-only access to SEC EDGAR + FRED + Polygon plus a citation-"
            "grounded 10-K extractor. Every fact returned by extract_tenk_section "
            "carries an Anthropic Citations API reference."
        ),
    )

    @mcp.tool(name="edgar.list_filings", description="List recent SEC filings for a CIK.")
    async def _edgar_list_filings(args: ListFilingsInput) -> list[EdgarFiling]:
        log.info("tool.start", tool="edgar.list_filings", cik=args.cik)
        return await list_filings(args.cik, form=args.form, limit=args.limit)

    @mcp.tool(name="edgar.company_facts", description="Fetch all XBRL facts for a CIK.")
    async def _edgar_company_facts(args: CompanyFactsInput) -> list[EdgarFact]:
        log.info("tool.start", tool="edgar.company_facts", cik=args.cik)
        return await fetch_company_facts(args.cik)

    @mcp.tool(name="fred.series", description="Fetch a FRED series with optional date window.")
    async def _fred_series(args: FredSeriesInput) -> FredSeries:
        log.info("tool.start", tool="fred.series", series=args.series_id)
        return await fetch_series(args.series_id, start=args.start, end=args.end)

    @mcp.tool(name="polygon.aggregates", description="Fetch OHLCV aggregate bars from Polygon.io.")
    async def _polygon_aggregates(args: PolygonAggregatesInput) -> list[PolygonAggregateBar]:
        log.info("tool.start", tool="polygon.aggregates", ticker=args.ticker)
        return await fetch_aggregates(
            args.ticker,
            multiplier=args.multiplier,
            timespan=args.timespan,
            start=args.start,
            end=args.end,
            adjusted=args.adjusted,
            limit=args.limit,
        )

    @mcp.tool(
        name="tenk.extract_section",
        description="Extract citation-grounded claims from a 10-K section.",
        meta={
            "ui": {
                "resourceUri": TENK_SUMMARY_CARD_RESOURCE_URI,
            }
        },
    )
    async def _tenk_extract(args: ExtractTenKInput) -> TenKExtractOutput:
        log.info(
            "tool.start",
            tool="tenk.extract_section",
            section=args.section.section,
            doc=args.section.document_title,
        )
        extraction = await extract_tenk_section(args.section, settings=s)
        ui = render_tenk_summary_card(
            TenKSummaryCardProps(
                extraction=extraction,
                cik=args.cik,
                company_name=args.company_name,
            )
        )
        log.info(
            "tool.end",
            tool="tenk.extract_section",
            n_facts=len(extraction.facts),
            cost_usd=extraction.cost_usd,
        )
        return TenKExtractOutput(extraction=extraction, ui=ui)

    log.info("server.build_done", tools=5)
    return mcp


def main() -> None:
    """CLI entry point. Binds the streamable-HTTP transport to the configured port."""
    configure_logging()
    settings = get_settings()
    log = get_logger("server")
    app = build_app(settings)
    log.info(
        "server.starting",
        host=settings.mcp_host,
        port=settings.mcp_port,
        transport="streamable-http",
    )
    app.run(transport="http", host=settings.mcp_host, port=settings.mcp_port)


if __name__ == "__main__":
    main()
