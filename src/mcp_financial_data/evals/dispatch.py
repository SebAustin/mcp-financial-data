"""Online eval dispatch: route each ``EvalCase`` to the real tool implementation.

Used when the harness runs without ``--offline``. Every tool return value is
normalized to the shape expected by ``evals/cases/seed.jsonl`` so
``exec_accuracy`` remains meaningful.
"""

from __future__ import annotations

from datetime import date
from typing import Any, cast

from mcp_financial_data.evals.types import EvalCase
from mcp_financial_data.extractors.tenk import TenKSection, extract_tenk_section
from mcp_financial_data.settings import Settings
from mcp_financial_data.tools.edgar import fetch_company_facts, list_filings
from mcp_financial_data.tools.fred import fetch_series
from mcp_financial_data.tools.polygon import Timespan, fetch_aggregates


class EvalDispatchError(Exception):
    """Raised when a case references an unknown tool or has invalid input."""


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)


async def dispatch_online(
    case: EvalCase, *, settings: Settings
) -> tuple[dict[str, Any], float, int, int]:
    """Execute ``case`` against live tools.

    Returns:
        ``(actual, cost_usd, input_tokens, output_tokens)``. Token counts are
        non-zero only for Anthropic-backed tools (the 10-K extractor).
    """
    tool = case.tool
    inp = case.input

    if tool == "edgar.list_filings":
        filings = await list_filings(
            str(inp["cik"]),
            form=inp.get("form"),
            limit=int(inp.get("limit", 40)),
        )
        return (
            {"filings": [f.model_dump(mode="json") for f in filings]},
            0.0,
            0,
            0,
        )

    if tool == "edgar.company_facts":
        facts = await fetch_company_facts(str(inp["cik"]))
        return (
            {"xbrl_facts": [f.model_dump(mode="json") for f in facts]},
            0.0,
            0,
            0,
        )

    if tool == "fred.series":
        series = await fetch_series(
            str(inp["series_id"]),
            start=_parse_date(inp.get("start")),
            end=_parse_date(inp.get("end")),
        )
        return ({"series": series.model_dump(mode="json")}, 0.0, 0, 0)

    if tool == "polygon.aggregates":
        bars = await fetch_aggregates(
            str(inp["ticker"]),
            multiplier=int(inp["multiplier"]),
            timespan=cast(Timespan, str(inp["timespan"])),
            start=date.fromisoformat(str(inp["start"])),
            end=date.fromisoformat(str(inp["end"])),
            adjusted=bool(inp.get("adjusted", True)),
            limit=int(inp.get("limit", 5000)),
        )
        return (
            {"bars": [b.model_dump(mode="json") for b in bars]},
            0.0,
            0,
            0,
        )

    if tool == "tenk.extract_section":
        section_payload = inp.get("section", inp)
        section = TenKSection.model_validate(section_payload)
        result = await extract_tenk_section(section, settings=settings)
        return (
            result.model_dump(mode="json"),
            result.cost_usd,
            result.input_tokens,
            result.output_tokens,
        )

    raise EvalDispatchError(f"unknown tool for online dispatch: {tool!r}")
