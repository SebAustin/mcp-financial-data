"""Tests for ``mcp_financial_data.tools._ratelimit``.

Per ADR 0006 and ``.cursor/rules/edgar-fair-access.mdc``, the limiter
must enforce strict pacing (no burst): minimum interval of ``1/rate``
between any two acquires. The end-to-end EDGAR rate-limit smoke test
that 30 concurrent EDGAR calls take >= 2.9 s lives in ``test_edgar.py``
so it exercises the real call path.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from mcp_financial_data.tools._ratelimit import TokenBucket


@pytest.mark.asyncio
async def test_token_bucket_first_acquire_is_immediate() -> None:
    bucket = TokenBucket(rate_per_sec=10)
    t0 = time.perf_counter()
    await bucket.acquire()
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.05, f"first acquire took {elapsed:.3f}s, expected <0.05s"


@pytest.mark.asyncio
async def test_token_bucket_paces_serial_calls() -> None:
    """10 sequential acquires must take >= 0.9 s wall-clock at rate=10/s.

    Matches the Fair Access rule's 10-concurrent smoke target.
    """
    bucket = TokenBucket(rate_per_sec=10)
    t0 = time.perf_counter()
    for _ in range(10):
        await bucket.acquire()
    elapsed = time.perf_counter() - t0
    assert elapsed >= 0.9, f"10 serial acquires took {elapsed:.3f}s, expected >=0.9s"


@pytest.mark.asyncio
async def test_token_bucket_30_concurrent_calls_take_at_least_2_9s() -> None:
    """ADR 0006: 30 concurrent acquires take >= 2.9 s under strict pacing."""
    bucket = TokenBucket(rate_per_sec=10)
    t0 = time.perf_counter()
    await asyncio.gather(*(bucket.acquire() for _ in range(30)))
    elapsed = time.perf_counter() - t0
    assert elapsed >= 2.9, f"30 concurrent acquires took {elapsed:.3f}s, expected >=2.9s"


@pytest.mark.asyncio
async def test_token_bucket_idle_does_not_accumulate_burst() -> None:
    """After a long idle, the next acquire is still immediate but the one
    after still pays the per-call interval.

    This is the "no-burst" property: idleness gives one free token but
    not a backlog of them.
    """
    bucket = TokenBucket(rate_per_sec=10)
    await bucket.acquire()  # consume the initial free token
    await asyncio.sleep(0.5)  # idle for 5 intervals worth of time
    t0 = time.perf_counter()
    # First post-idle acquire is immediate.
    await bucket.acquire()
    immediate = time.perf_counter() - t0
    assert immediate < 0.05, f"post-idle immediate acquire took {immediate:.3f}s"
    # But the one right after must be paced.
    t1 = time.perf_counter()
    await bucket.acquire()
    paced = time.perf_counter() - t1
    assert paced >= 0.08, f"paced acquire took {paced:.3f}s, expected >=0.08s"


def test_token_bucket_rejects_non_positive_rate() -> None:
    with pytest.raises(ValueError, match="rate"):
        TokenBucket(rate_per_sec=0)
    with pytest.raises(ValueError, match="rate"):
        TokenBucket(rate_per_sec=-1)
