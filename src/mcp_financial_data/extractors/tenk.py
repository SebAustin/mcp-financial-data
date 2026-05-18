"""Citation-grounded 10-K extractor backed by Anthropic Claude Sonnet 4.5.

Hard contract (see ``.cursor/rules/citations.mdc``): every fact returned by
``extract_tenk_section`` carries at least one Anthropic Citations API
reference. Uncited model output is dropped or moved to ``notes`` with an
``[INFERENCE]`` prefix — never surfaced as a fact.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from mcp_financial_data.settings import Settings, get_settings

TenKSectionName = Literal[
    "item_1_business",
    "item_1a_risk_factors",
    "item_7_mdna",
    "item_7a_market_risk",
    "item_8_financial_statements",
]

DEFAULT_MAX_TOKENS: Final[int] = 4096


class ExtractorSpendCapError(Exception):
    """Raised when the extractor would exceed ``MAX_API_SPEND_USD``."""


class Citation(BaseModel):
    """Anthropic Citations API reference into a source document."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_title: str = Field(..., min_length=1)
    start_char_index: int = Field(..., ge=0)
    end_char_index: int = Field(..., ge=0)
    cited_text: str = Field(..., min_length=1)


class CitedClaim(BaseModel):
    """One factual claim with at least one citation. THE primary output type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str = Field(..., min_length=1)
    citations: tuple[Citation, ...] = Field(..., min_length=1)


class TenKSection(BaseModel):
    """A 10-K section's input bundle to the extractor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    section: TenKSectionName
    document_title: str = Field(..., min_length=1, description="e.g. 'AAPL 10-K FY2025 Item 1A'.")
    text: str = Field(..., min_length=1)


class ExtractionResult(BaseModel):
    """Full extractor output for one section."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    section: TenKSectionName
    document_title: str
    facts: tuple[CitedClaim, ...] = ()
    notes: tuple[str, ...] = Field(
        default=(),
        description="Uncited or partially supported model output, prefixed [INFERENCE].",
    )
    model: str
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)


async def extract_tenk_section(
    section: TenKSection,
    *,
    settings: Settings | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> ExtractionResult:
    """Extract citation-grounded claims from a 10-K section using Claude.

    Implementation in ``prompts/03_tenk_citations_extractor.md``. The stub
    enforces only the spend-cap check so the cap path is testable today.

    Raises:
        ExtractorSpendCapError: if ``MAX_API_SPEND_USD`` has been reached.
    """
    s = settings or get_settings()
    if s.max_api_spend_usd <= 0:
        raise ExtractorSpendCapError(
            f"MAX_API_SPEND_USD={s.max_api_spend_usd} bars new Anthropic calls"
        )
    _ = (section, max_tokens)
    raise NotImplementedError("see prompts/03_tenk_citations_extractor.md")
