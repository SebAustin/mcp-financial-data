# ADR 0007 — 10-K extractor pricing table + process-local spend cap

* Status: Accepted
* Date: 2026-05-19
* Deciders: Sebastien Henry

## Context and Problem Statement

The 10-K extractor calls Claude Sonnet 4.6 with the Anthropic **Citations
API** for every section it processes (see ADR 0003). One eval `--full` run
across the seed cases is hundreds of thousands of tokens; one hiring-manager
demo can be the same on top. Two failure modes must be prevented:

1. **Runaway spend.** Anthropic credits are non-trivial. The master
   `.cursorrules` §P5 mandates an `MAX_API_SPEND_USD` cap enforced *inside*
   the extractor and the eval harness — not just on the dashboard.
2. **Silent under-billing.** If the extractor estimates cost via a stale
   pricing table or — worse — a hard-coded constant divorced from the model
   id Anthropic returned, the cap is meaningless. The reported `cost_usd`
   on `ExtractionResult` must match the bill.

The existing day-0 stub only checked `max_api_spend_usd <= 0`. That is
necessary for the unit test but not sufficient for real use: a process that
starts with a healthy cap and burns through it during a long `--full` run
must stop on its own.

## Decision Drivers

* Master `.cursorrules` §P5 — `MAX_API_SPEND_USD` is enforced in the
  extractor AND the eval harness; CI defaults to `--offline`.
* Master `.cursorrules` §6 — no hidden prices in inline JSON or scattered
  constants; the table lives next to the call site.
* Master `.cursorrules` §8 (Reproducibility) — each eval row records the
  cost; same SHA + same fixtures = same cost.
* The Anthropic SDK does not expose published prices programmatically. We
  must keep our own table and refresh it when Anthropic updates pricing.

## Considered Options

* **Estimate cost from a hard-coded `COST_PER_TOKEN` constant.** Simplest
  but the constant rots silently when Anthropic publishes a new price or
  when we change the model id. Rejected.
* **Skip the pricing table and use the SDK's `response.usage` only.** The
  SDK reports token counts, not USD. We would still need a table to
  multiply by. Rejected.
* **Per-model pricing dataclass in `extractors/_pricing.py` + an explicit
  `UnknownModelPricingError` on lookup miss.** A new model id makes CI
  fail loudly. Selected.
* **Cap enforced only by Anthropic's billing dashboard.** Trust-based, not
  code-based. The whole point of the spend cap is to prove to a reviewer
  that the cap is enforced in code. Rejected.
* **Cap enforced via a per-call `httpx` interceptor.** Mixes concerns and
  hides the cap behind the SDK transport. Rejected; the explicit
  pre-call / post-call check is more readable.

## Decision Outcome

### Pricing table

A private module `src/mcp_financial_data/extractors/_pricing.py` exposes:

```python
@dataclass(frozen=True, slots=True)
class ModelPricing:
    input_per_mtok: float
    output_per_mtok: float
    def cost_usd(self, *, input_tokens: int, output_tokens: int) -> float: ...

def get_model_pricing(model_id: str) -> ModelPricing: ...
def estimate_cost_usd(model_id: str, *, input_tokens: int, output_tokens: int) -> float: ...
```

* Numbers are USD per **million tokens**, the unit Anthropic publishes.
* `PRICE_TABLE_VERSION` is a date string. Bump it when the table changes.
* The current table covers portfolio fixture ids (`claude-sonnet-4-6-20260301`,
  `claude-opus-4-7-20260301`), live API ids (`claude-sonnet-4-6`,
  `claude-opus-4-7`), and **prefix fallback** for dated snapshot ids returned
  by Anthropic (e.g. `claude-sonnet-4-6-20250929`).
* `UnknownModelPricingError` is a `KeyError` subclass — Anthropic returning
  an unfamiliar model id is fatal, not estimated. The eval harness catches it
  before the offline-fixture `KeyError` handler and surfaces
  `case.pricing_error`.

### Spend cap

`extractors/tenk.py` owns a process-local `_total_spend_usd` counter
guarded by a `threading.Lock` (defensive — the extractor itself is async,
but the harness may run multiple loops in the same process). The cap is
enforced in two places:

1. **Before each call** (`_enforce_spend_cap`): raises
   `ExtractorSpendCapError` if `max_api_spend_usd <= 0` (the cap-set-to-zero
   path the unit test pins) OR if the running counter has already met or
   exceeded the cap.
2. **After each call**: the actual `cost_usd` is added to the counter via
   `_add_spend`. The next call then sees the new total.

Tests reset the counter via `reset_spend_counter()`. Production never calls
this — once a process is at the cap, it stays at the cap until the operator
relaunches.

The cap is intentionally **conservative**. We do not pre-estimate the cost
of the next call and refuse it if the projected total would exceed the cap.
The reasoning: pre-estimation requires knowing `output_tokens`, which we do
not until the call returns; and a tight budget that allows one over-cap call
is better than a sloppy budget that blocks the call we wanted.

### Logging

Every extraction logs `extractor.start` and `extractor.done` events
including `cost_usd` and the cumulative `total_spend_usd`. Operators can
ship the latter to Datadog and alert on it independently of the in-process
cap.

## Consequences

* The extractor's `cost_usd` field is now a fact, not a guess; the eval
  harness's `total_cost_usd` summary row is comparable across runs.
* Adding a new Anthropic model requires touching `_pricing.py` once. The
  test suite catches the omission because `extract_tenk_section` raises
  `UnknownModelPricingError` for an unmapped model id.
* CI never exercises the cap path because `--offline` short-circuits
  before the Anthropic call. The cap exists for `--full` runs and demos.
* A future PR can add a per-call **projected-cost** check (cap minus
  current minus the prompt token estimate) without changing the public
  contract. Today we accept the small over-shoot risk to keep the logic
  obvious.
* The pricing table is operator-maintained. Bumping `PRICE_TABLE_VERSION`
  is part of any pricing change.

## References

* https://docs.anthropic.com/en/docs/build-with-claude/citations — Citations API.
* https://www.anthropic.com/pricing — Sonnet / Opus list prices.
* ADR 0003 — Citations required for every extracted 10-K claim.
* `.cursorrules` §P5 — spend-cap mandate.
* `prompts/03_tenk_citations_extractor.md` — implementation contract.
