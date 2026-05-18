"""Structlog setup. JSON renderer in production, console renderer in dev.

Import order in entrypoints::

    from mcp_financial_data.logging import configure_logging
    configure_logging()
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from mcp_financial_data.settings import get_settings


def _add_service_metadata(
    _logger: logging.Logger, _method: str, event_dict: EventDict
) -> EventDict:
    """Stamp every record with the service name and version."""
    event_dict.setdefault("service", "mcp-financial-data")
    from mcp_financial_data import __version__

    event_dict.setdefault("service_version", __version__)
    return event_dict


def configure_logging() -> None:
    """Configure structlog + stdlib logging once per process. Idempotent."""
    settings = get_settings()
    log_level = getattr(logging, settings.log_level)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _add_service_metadata,
    ]

    final_processor: Processor
    if settings.log_format == "json":
        final_processor = structlog.processors.JSONRenderer(sort_keys=True)
    else:
        final_processor = structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            final_processor,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        level=log_level,
        stream=sys.stderr,
        format="%(message)s",
        force=True,
    )


def get_logger(name: str | None = None) -> Any:
    """Return a bound structlog logger. Convenience over ``structlog.get_logger``."""
    return structlog.get_logger(name) if name else structlog.get_logger()
