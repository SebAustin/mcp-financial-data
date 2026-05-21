"""Citation-grounded 10-K extractor backed by Anthropic Claude Sonnet 4.5.

Hard contract (see ``.cursor/rules/citations.mdc`` and ADR 0003):

* Every fact returned by ``extract_tenk_section`` is a ``CitedClaim`` with at
  least one ``Citation`` produced by the Anthropic **Citations API**.
* Uncited model output goes into ``notes`` prefixed with ``[INFERENCE]`` —
  it is never surfaced as a fact.
* Facts whose ``cited_text`` does not appear verbatim in the source section
  are dropped (the failure mode the Citations API itself can produce when
  the model paraphrases the cited span beyond the document's text).
* Process-local spend accumulator enforces ``MAX_API_SPEND_USD``. CI runs
  ``--offline`` so this path is never exercised there.

Implementation reference: ``prompts/03_tenk_citations_extractor.md`` and
ADR 0007 (extractor pricing + spend cap).
"""

from __future__ import annotations

import threading
import time
from typing import Any, Final, Literal

import anthropic
from anthropic.types import (
    DocumentBlockParam,
    Message,
    TextBlock,
    TextBlockParam,
)
from pydantic import BaseModel, ConfigDict, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from mcp_financial_data.extractors._pricing import (
    UnknownModelPricingError,
    estimate_cost_usd,
    resolve_api_model_id,
)
from mcp_financial_data.logging import get_logger
from mcp_financial_data.settings import Settings, get_settings

TenKSectionName = Literal[
    "item_1_business",
    "item_1a_risk_factors",
    "item_7_mdna",
    "item_7a_market_risk",
    "item_8_financial_statements",
]

DEFAULT_MAX_TOKENS: Final[int] = 4096
DEFAULT_SYSTEM_PROMPT: Final[str] = (
    "You are extracting risk factors and material claims from a U.S. SEC "
    "10-K filing. Reply with one short factual sentence per claim, drawn "
    "directly from the supplied document. Every claim MUST be grounded in "
    "a citation; if you cannot cite a span, do not make the claim."
)

_INFERENCE_PREFIX: Final[str] = "[INFERENCE]"
_log = get_logger("extractors.tenk")


class ExtractorSpendCapError(Exception):
    """Raised when the extractor would exceed ``MAX_API_SPEND_USD``."""


class ExtractorConfigError(Exception):
    """Raised when required configuration (e.g. ``ANTHROPIC_API_KEY``) is missing."""


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
    latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Wall-clock milliseconds for the Anthropic round-trip.",
    )


# ---------------------------------------------------------------------------
# Process-local spend counter. The cap is enforced both BEFORE and AFTER a
# call: before, to short-circuit when we are already at/over budget; after,
# to record actual usage. Tests reset via ``reset_spend_counter()``.
# ---------------------------------------------------------------------------
_spend_lock = threading.Lock()
_total_spend_usd: float = 0.0


def get_total_spend_usd() -> float:
    """Return the cumulative USD spend recorded by this process."""
    with _spend_lock:
        return _total_spend_usd


def reset_spend_counter() -> None:
    """Zero the cumulative spend counter. Intended for tests only."""
    global _total_spend_usd
    with _spend_lock:
        _total_spend_usd = 0.0


def _add_spend(amount_usd: float) -> float:
    """Atomically add to the spend counter and return the new total."""
    global _total_spend_usd
    with _spend_lock:
        _total_spend_usd += amount_usd
        return _total_spend_usd


def _enforce_spend_cap(settings: Settings) -> None:
    """Raise ``ExtractorSpendCapError`` if the cap is already exhausted."""
    cap = settings.max_api_spend_usd
    if cap <= 0:
        raise ExtractorSpendCapError(f"MAX_API_SPEND_USD={cap} bars new Anthropic calls")
    current = get_total_spend_usd()
    if current >= cap:
        raise ExtractorSpendCapError(
            f"MAX_API_SPEND_USD={cap:.4f} exhausted "
            f"(spent={current:.4f}); refusing new Anthropic call"
        )


def _build_client(settings: Settings) -> anthropic.AsyncAnthropic:
    """Construct an ``AsyncAnthropic`` client with SDK-level retries off.

    We layer ``tenacity`` on top so the retry policy is one place, not two.
    """
    if settings.anthropic_api_key is None:
        raise ExtractorConfigError("ANTHROPIC_API_KEY is required to call the 10-K extractor")
    return anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key.get_secret_value(),
        max_retries=0,
    )


def _document_block(section: TenKSection) -> DocumentBlockParam:
    """Build the Anthropic ``document`` content block with citations enabled."""
    return {
        "type": "document",
        "source": {
            "type": "text",
            "media_type": "text/plain",
            "data": section.text,
        },
        "title": section.document_title,
        "context": f"10-K {section.section} for {section.document_title}",
        "citations": {"enabled": True},
    }


def _user_instruction_block(section: TenKSection) -> TextBlockParam:
    """Short user-turn instruction. Kept terse so it does not dominate cost."""
    return {
        "type": "text",
        "text": (
            f"Extract the material claims from the supplied {section.section} "
            "section. Reply with one short factual sentence per claim. "
            "Every claim must be cited."
        ),
    }


_RETRYABLE_EXCEPTIONS = (
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
)


@retry(
    reraise=True,
    retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
)
async def _call_anthropic(
    client: anthropic.AsyncAnthropic,
    *,
    model: str,
    max_tokens: int,
    section: TenKSection,
) -> Message:
    """Single ``messages.create`` round-trip; retried on 429/5xx/timeouts."""
    return await client.messages.create(
        model=resolve_api_model_id(model),
        max_tokens=max_tokens,
        system=DEFAULT_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    _document_block(section),
                    _user_instruction_block(section),
                ],
            }
        ],
    )


def _normalize_citation(raw: object, *, document_title: str) -> Citation | None:
    """Map an Anthropic citation object into our ``Citation`` schema.

    Returns ``None`` for citation shapes we do not yet support (e.g. page
    or content-block locations). Char-location is the only shape produced by
    text/plain documents today.
    """
    cited_text = getattr(raw, "cited_text", None)
    start = getattr(raw, "start_char_index", None)
    end = getattr(raw, "end_char_index", None)
    title = getattr(raw, "document_title", None) or document_title
    if not isinstance(cited_text, str) or not cited_text:
        return None
    if not isinstance(start, int) or not isinstance(end, int):
        return None
    try:
        return Citation(
            document_title=title,
            start_char_index=start,
            end_char_index=end,
            cited_text=cited_text,
        )
    except ValueError:
        return None


def _citations_anchor(citations: tuple[Citation, ...]) -> tuple[tuple[str, int, int], ...]:
    """Stable key used to merge consecutive text blocks that share citations."""
    return tuple((c.document_title, c.start_char_index, c.end_char_index) for c in citations)


def _parse_response(
    response: Message, *, section: TenKSection
) -> tuple[tuple[CitedClaim, ...], tuple[str, ...]]:
    """Split the model output into cited ``facts`` and uncited ``notes``.

    Consecutive text blocks that share the same citation anchors are merged
    into one ``CitedClaim``. A claim whose ``cited_text`` does not appear in
    the source section is dropped (a Citations API failure mode we want to
    surface as "the model lied about its source" rather than as a fact).
    """
    facts: list[CitedClaim] = []
    notes: list[str] = []
    pending: dict[str, Any] | None = None

    def _flush() -> None:
        nonlocal pending
        if pending is None:
            return
        text = pending["text"].strip()
        citations: tuple[Citation, ...] = tuple(pending["citations"])
        pending = None
        if not text:
            return
        if not citations:
            notes.append(f"{_INFERENCE_PREFIX} {text}")
            return
        good = tuple(c for c in citations if c.cited_text in section.text)
        if not good:
            _log.warning(
                "extractor.citation_not_in_source",
                document_title=section.document_title,
                cited_texts=[c.cited_text[:60] for c in citations],
            )
            return
        facts.append(CitedClaim(text=text, citations=good))

    for block in response.content:
        if not isinstance(block, TextBlock):
            continue
        text = block.text or ""
        raw_citations = list(block.citations or [])
        norm = tuple(
            c
            for c in (
                _normalize_citation(r, document_title=section.document_title) for r in raw_citations
            )
            if c is not None
        )
        if not norm:
            _flush()
            stripped = text.strip()
            if stripped:
                notes.append(f"{_INFERENCE_PREFIX} {stripped}")
            continue
        anchor = _citations_anchor(norm)
        if pending is not None and pending["anchor"] == anchor:
            pending["text"] += text
        else:
            _flush()
            pending = {"text": text, "citations": list(norm), "anchor": anchor}
    _flush()
    return tuple(facts), tuple(notes)


async def extract_tenk_section(
    section: TenKSection,
    *,
    settings: Settings | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    client: anthropic.AsyncAnthropic | None = None,
) -> ExtractionResult:
    """Extract citation-grounded claims from a 10-K section using Claude.

    Args:
        section: The 10-K section to extract from. Sent as one ``document``
            content block with ``citations={"enabled": True}``.
        settings: Optional override; defaults to the process-cached settings.
        max_tokens: Maximum completion tokens. Defaults to ``DEFAULT_MAX_TOKENS``.
        client: Optional injected ``AsyncAnthropic`` client. When ``None`` the
            extractor constructs a fresh one from settings; tests use ``respx``
            to mock the HTTP layer instead of injecting a fake client.

    Raises:
        ExtractorSpendCapError: if ``MAX_API_SPEND_USD`` has been reached.
        ExtractorConfigError: if ``ANTHROPIC_API_KEY`` is missing.
        UnknownModelPricingError: if the response model id is absent from the
            pricing table — we refuse to silently estimate.
    """
    s = settings or get_settings()
    _enforce_spend_cap(s)

    model_id = s.anthropic_model_primary
    owns_client = client is None
    if owns_client:
        client = _build_client(s)
    assert client is not None

    _log.info(
        "extractor.start",
        section=section.section,
        document_title=section.document_title,
        model=model_id,
        max_tokens=max_tokens,
    )

    t0 = time.perf_counter()
    try:
        response = await _call_anthropic(
            client,
            model=model_id,
            max_tokens=max_tokens,
            section=section,
        )
    finally:
        if owns_client:
            await client.close()

    facts, notes = _parse_response(response, section=section)
    latency_ms = (time.perf_counter() - t0) * 1000.0

    input_tokens = int(response.usage.input_tokens)
    output_tokens = int(response.usage.output_tokens)
    try:
        cost_usd = estimate_cost_usd(
            response.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    except UnknownModelPricingError:
        _log.error("extractor.unknown_model_pricing", model=response.model)
        raise
    new_total = _add_spend(cost_usd)

    _log.info(
        "extractor.done",
        section=section.section,
        document_title=section.document_title,
        model=response.model,
        n_facts=len(facts),
        n_notes=len(notes),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        total_spend_usd=new_total,
    )

    return ExtractionResult(
        section=section.section,
        document_title=section.document_title,
        facts=facts,
        notes=notes,
        model=response.model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
    )
