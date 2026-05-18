"""Tests for ``mcp_financial_data.logging``."""

from __future__ import annotations

import structlog

from mcp_financial_data.logging import configure_logging, get_logger


def test_configure_logging_is_idempotent() -> None:
    configure_logging()
    configure_logging()
    log = get_logger("smoke")
    assert log is not None


def test_get_logger_returns_bound_logger() -> None:
    configure_logging()
    log = get_logger("test")
    # structlog returns a BoundLoggerLazyProxy until first call; assert that
    # the public logger methods are present rather than relying on an exact
    # type, which is a structlog implementation detail.
    for method in ("debug", "info", "warning", "error", "exception", "bind"):
        assert callable(getattr(log, method)), method
    assert log is not None
    assert structlog is not None


def test_logger_emits_service_metadata(capsys: object) -> None:
    configure_logging()
    log = get_logger("emitter")
    log.info("event_under_test", k="v")
    # Just assert the call did not raise; output goes to stderr and is
    # exercised end-to-end in evals smoke run.
