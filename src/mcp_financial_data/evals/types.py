"""Shared eval harness types (avoids import cycles between harness and dispatch)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EvalCase:
    """One row from the seed JSONL set."""

    id: str
    tool: str
    description: str
    input: dict[str, Any]
    expected: dict[str, Any]
