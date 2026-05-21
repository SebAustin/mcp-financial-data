"""Canned tool responses used by the eval harness in ``--offline`` mode.

Each fixture is keyed by ``case_id`` and matches the shape of the tool's
output model. Real network calls land in W1 follow-up
``prompts/02_edgar_client.md`` / ``prompts/03_tenk_citations_extractor.md``;
this file is here so CI can produce numeric scores without secrets.
"""

from __future__ import annotations

from typing import Any

OFFLINE_FIXTURES: dict[str, dict[str, Any]] = {
    "edgar-aapl-list-10k-2025": {
        "filings": [
            {
                "cik": "0000320193",
                "accession_number": "0000320193-25-000079",
                "form": "10-K",
                "filing_date": "2025-10-31",
                "primary_document": "aapl-20250927.htm",
            }
        ],
    },
    "edgar-msft-revenues-fy2025": {
        "xbrl_facts": [
            {
                "cik": "0000789019",
                "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
                "unit": "USD",
                "value": 281_724_000_000.0,
                "fiscal_year": 2025,
                "fiscal_period": "FY",
                "end_date": "2025-06-30",
                "accession_number": "0000950170-25-100235",
            }
        ],
    },
    "edgar-googl-list-8k-2025": {
        "filings": [
            {
                "cik": "0001652044",
                "accession_number": "0001193125-26-216986",
                "form": "8-K",
                "filing_date": "2026-05-11",
                "primary_document": "d109021d8k.htm",
            }
        ],
    },
    "fred-gdp-q1-2025": {
        "series": {
            "series_id": "GDP",
            "title": "Gross Domestic Product",
            "frequency": "Quarterly",
            "units": "Billions of Dollars",
            "observations": [
                {
                    "series_id": "GDP",
                    "observation_date": "2025-01-01",
                    "value": 30_042.113,
                }
            ],
        }
    },
    "tenk-aapl-risk-factors": {
        "section": "item_1a_risk_factors",
        "document_title": "AAPL 10-K FY2025 Item 1A",
        "facts": [
            {
                "text": (
                    "The Company's business depends on the timely receipt and "
                    "successful integration of components and finished products "
                    "from third-party manufacturers."
                ),
                "citations": [
                    {
                        "document_title": "AAPL 10-K FY2025 Item 1A",
                        "start_char_index": 0,
                        "end_char_index": 180,
                        "cited_text": (
                            "The Company's business depends on the timely "
                            "receipt and successful integration of components"
                        ),
                    }
                ],
            },
            {
                "text": (
                    "The Company is exposed to global macroeconomic conditions, "
                    "including inflation, interest rates, and foreign exchange "
                    "fluctuations."
                ),
                "citations": [
                    {
                        "document_title": "AAPL 10-K FY2025 Item 1A",
                        "start_char_index": 200,
                        "end_char_index": 360,
                        "cited_text": (
                            "exposed to global macroeconomic conditions, "
                            "including inflation, interest rates"
                        ),
                    }
                ],
            },
        ],
        "notes": (),
        "model": "claude-sonnet-4-5-20260301",
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "latency_ms": 0.0,
    },
}


def get_offline_fixture(case_id: str) -> dict[str, Any]:
    """Return the canned response for ``case_id`` or raise KeyError."""
    if case_id not in OFFLINE_FIXTURES:
        msg = f"No offline fixture for case_id={case_id!r}; add one to fixtures.py"
        raise KeyError(msg)
    return OFFLINE_FIXTURES[case_id]
