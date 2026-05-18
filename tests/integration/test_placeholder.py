"""Integration tests live here. Skipped by default — run with `make test-int`."""

from __future__ import annotations

import pytest


@pytest.mark.integration
def test_real_network_placeholder() -> None:
    """Placeholder so pytest finds the integration marker. Replaced in W1."""
    assert True
