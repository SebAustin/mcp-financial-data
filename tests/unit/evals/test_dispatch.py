"""Tests for online eval dispatch helpers."""

from __future__ import annotations

from datetime import date

from mcp_financial_data.evals.dispatch import _filter_xbrl_facts_for_eval
from mcp_financial_data.tools.edgar import EdgarFact


def _fact(*, concept: str, fiscal_year: int) -> EdgarFact:
    return EdgarFact(
        cik="0000789019",
        concept=concept,
        unit="USD",
        value=1.0,
        fiscal_year=fiscal_year,
        fiscal_period="FY",
        end_date=date(2025, 6, 30),
        accession_number="0000789019-25-000010",
    )


def test_filter_xbrl_facts_for_eval_matches_expected_concept_and_year() -> None:
    facts = [
        _fact(concept="Revenues", fiscal_year=2025),
        _fact(concept="Revenues", fiscal_year=2024),
        _fact(concept="Assets", fiscal_year=2025),
    ]
    expected = {
        "xbrl_facts": [
            {
                "concept": "Revenues",
                "fiscal_year": 2025,
            }
        ]
    }
    filtered = _filter_xbrl_facts_for_eval(facts, expected)
    assert len(filtered) == 1
    assert filtered[0].concept == "Revenues"
    assert filtered[0].fiscal_year == 2025
