"""Anthropic token pricing table for the 10-K extractor.

Kept private to ``extractors`` so the pricing constants are versioned next to
the call site that uses them. The eval harness reads ``cost_usd`` off the
``ExtractionResult`` rather than re-computing — so this table is the single
source of truth for extractor spend.

Numbers are USD per **million** tokens, the unit Anthropic publishes on
``https://www.anthropic.com/pricing``. ``cost_usd`` is a pure function of the
returned ``usage.input_tokens`` and ``usage.output_tokens``; no batching, no
prompt-cache discount applied here (those reductions are handled separately
by the SDK and surfaced as ``cache_read_input_tokens`` if/when we opt in).

If Anthropic publishes a new price, bump ``PRICE_TABLE_VERSION`` and add a
new row keyed by the model id we passed to ``messages.create``. The extractor
raises ``UnknownModelPricingError`` rather than silently estimating, so a
forgotten update fails loudly in CI rather than under-billing the spend cap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

PRICE_TABLE_VERSION: Final[str] = "2026-05-19"


@dataclass(frozen=True, slots=True)
class ModelPricing:
    """USD per million tokens for one Anthropic model id."""

    input_per_mtok: float
    output_per_mtok: float

    def cost_usd(self: ModelPricing, *, input_tokens: int, output_tokens: int) -> float:
        """Compute total USD cost for one ``messages.create`` response.

        Args:
            input_tokens: Non-cached prompt tokens billed by Anthropic.
            output_tokens: Completion tokens returned by the model.
        """
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError(
                f"token counts must be non-negative; got "
                f"input={input_tokens}, output={output_tokens}"
            )
        million = 1_000_000.0
        return round(
            (input_tokens / million) * self.input_per_mtok
            + (output_tokens / million) * self.output_per_mtok,
            6,
        )


class UnknownModelPricingError(KeyError):
    """Raised when the extractor returns a model id absent from the table."""


# Sonnet 4.6 + Opus 4.7 published list prices, May 2026. Citations API does
# not change the per-token price; document tokens are billed as input.
_SONNET_46 = ModelPricing(input_per_mtok=3.00, output_per_mtok=15.00)
_OPUS_47 = ModelPricing(input_per_mtok=15.00, output_per_mtok=75.00)

# Portfolio fixtures use dated ids; the live Anthropic API uses dateless ids
# (see https://platform.claude.com/docs/en/about-claude/models/model-ids).
_PORTFOLIO_MODEL_ALIASES: Final[dict[str, str]] = {
    "claude-sonnet-4-6-20260301": "claude-sonnet-4-6",
    "claude-opus-4-7-20260301": "claude-opus-4-7",
}

_PRICE_TABLE: Final[dict[str, ModelPricing]] = {
    "claude-sonnet-4-6-20260301": _SONNET_46,
    "claude-sonnet-4-6": _SONNET_46,
    "claude-opus-4-7-20260301": _OPUS_47,
    "claude-opus-4-7": _OPUS_47,
}

# Anthropic returns dated snapshot ids (``claude-sonnet-4-6-20250929``). Match
# longest prefix first for ids absent from the explicit table above.
_PRICING_PREFIXES: Final[tuple[tuple[str, ModelPricing], ...]] = (
    ("claude-opus-4-7", _OPUS_47),
    ("claude-sonnet-4-6", _SONNET_46),
)


def resolve_api_model_id(model_id: str) -> str:
    """Map portfolio fixture ids to live Anthropic API model ids."""
    return _PORTFOLIO_MODEL_ALIASES.get(model_id, model_id)


def get_model_pricing(model_id: str) -> ModelPricing:
    """Return the published pricing for ``model_id`` or raise."""
    for candidate in (model_id, resolve_api_model_id(model_id)):
        if candidate in _PRICE_TABLE:
            return _PRICE_TABLE[candidate]
    normalized = resolve_api_model_id(model_id)
    for prefix, pricing in _PRICING_PREFIXES:
        if normalized == prefix or normalized.startswith(f"{prefix}-"):
            return pricing
    raise UnknownModelPricingError(
        f"No pricing row for model_id={model_id!r}; "
        f"add one to extractors/_pricing.py (table v{PRICE_TABLE_VERSION})."
    )


def estimate_cost_usd(model_id: str, *, input_tokens: int, output_tokens: int) -> float:
    """Convenience: look up pricing then compute total USD."""
    return get_model_pricing(model_id).cost_usd(
        input_tokens=input_tokens, output_tokens=output_tokens
    )
