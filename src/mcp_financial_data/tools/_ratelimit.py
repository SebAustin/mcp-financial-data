"""Process-shared rate-limit primitives for the EDGAR client.

Per ADR 0006 and ``.cursor/rules/edgar-fair-access.mdc``, every EDGAR
request must traverse:

1. ``EDGAR_CONCURRENCY`` — an ``asyncio.Semaphore(10)`` that caps the
   number of in-flight EDGAR HTTP requests at any moment.
2. ``EDGAR_TOKEN_BUCKET`` — a strict-pacing limiter sized at 10
   requests / second sustained (minimum 100 ms between any two acquires).

These live at module scope so all callers in the same process share the
same limiter, even across multiple ``httpx.AsyncClient`` instances.

FRED and Polygon are NOT gated through these limiters; their per-key
quotas are managed by their operators.
"""

from __future__ import annotations

import asyncio
import time
from typing import Final

#: SEC Fair Access ceiling. Never set higher than 10 without an ADR update.
EDGAR_MAX_PER_SEC: Final[int] = 10


class TokenBucket:
    """Strict-pacing rate limiter (no burst).

    Tracks a single monotonic ``_next_allowed`` cursor. On each
    ``acquire()``:

    1. If ``time.monotonic() < _next_allowed``: sleep the difference.
    2. Set ``_next_allowed = max(now, _next_allowed) + 1/rate``.

    The "no-burst" property matters: idleness gives one free token (the
    very next call is immediate) but not a backlog of free tokens. This
    matches the SEC's "10 concurrent calls take >= 0.9 s" Fair Access
    smoke target rather than allowing a 10-burst that would saturate
    EDGAR's edge in a single asyncio scheduler tick.
    """

    def __init__(self: TokenBucket, rate_per_sec: int) -> None:
        if rate_per_sec <= 0:
            raise ValueError(f"rate_per_sec must be positive, got {rate_per_sec!r}")
        self._rate = rate_per_sec
        self._min_interval = 1.0 / float(rate_per_sec)
        self._next_allowed = 0.0
        self._lock = asyncio.Lock()

    @property
    def rate_per_sec(self: TokenBucket) -> int:
        return self._rate

    async def acquire(self: TokenBucket) -> None:
        """Block until the next pacing slot, then reserve the one after."""
        async with self._lock:
            now = time.monotonic()
            if now < self._next_allowed:
                await asyncio.sleep(self._next_allowed - now)
                now = time.monotonic()
            self._next_allowed = now + self._min_interval


#: Process-shared EDGAR concurrency cap. Acquire via ``async with``.
EDGAR_CONCURRENCY: Final[asyncio.Semaphore] = asyncio.Semaphore(EDGAR_MAX_PER_SEC)

#: Process-shared EDGAR token bucket. Acquire via ``await .acquire()``.
EDGAR_TOKEN_BUCKET: Final[TokenBucket] = TokenBucket(rate_per_sec=EDGAR_MAX_PER_SEC)
