"""Process-shared KV cache for tool HTTP responses.

Per ADR 0006, EDGAR / FRED / Polygon GET responses are cached for 24 h.
This module defines the contract — :class:`CacheStore` — and ships one
implementation, :class:`SqliteCache`, backed by stdlib ``sqlite3``
wrapped in ``asyncio.to_thread``. A Postgres-backed implementation of the
same Protocol lands in a follow-up PR.

The cache key for GET requests is the absolute URL. The Accept header is
not part of the key because the data APIs we hit return the same body
regardless. TTL is stored absolutely (epoch seconds), not relatively, so
two processes that share the same SQLite file agree on expiry.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Final, Protocol, runtime_checkable

from mcp_financial_data.settings import Settings

DEFAULT_CACHE_TTL_SECONDS: Final[int] = 24 * 60 * 60

#: Default on-disk location for the SQLite cache. Project-relative so a
#: developer running ``make ci`` from the repo root gets the same path as
#: the eval harness.
DEFAULT_CACHE_PATH: Final[Path] = Path("evals") / ".cache.sqlite"

_SCHEMA: Final[str] = """
CREATE TABLE IF NOT EXISTS cache (
    key        TEXT PRIMARY KEY,
    value      BLOB NOT NULL,
    expires_at REAL NOT NULL
)
"""


@runtime_checkable
class CacheStore(Protocol):
    """Async key-value store with TTL semantics.

    Implementations must:

    - Return ``None`` on miss and on expired entries.
    - Persist ``value`` exactly (bytes-in, bytes-out).
    - Treat ``ttl_seconds`` as an absolute lifetime from the moment of
      ``set``, measured against wall-clock time.
    """

    async def get(self: CacheStore, key: str) -> bytes | None: ...
    async def set(self: CacheStore, key: str, value: bytes, *, ttl_seconds: int) -> None: ...


class SqliteCache:
    """``CacheStore`` backed by stdlib ``sqlite3`` + ``asyncio.to_thread``.

    The connection is opened per call (``with sqlite3.connect(...)``) so
    we never share a connection across threads — sqlite3 connections are
    thread-affine by default, and ``asyncio.to_thread`` hands the work
    off to whichever worker is free.
    """

    def __init__(self: SqliteCache, path: Path) -> None:
        self._path = path

    @property
    def path(self: SqliteCache) -> Path:
        return self._path

    async def get(self: SqliteCache, key: str) -> bytes | None:
        import asyncio

        return await asyncio.to_thread(self._get_sync, key)

    async def set(self: SqliteCache, key: str, value: bytes, *, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            raise ValueError(f"ttl_seconds must be positive, got {ttl_seconds!r}")
        import asyncio

        expires_at = time.time() + ttl_seconds
        await asyncio.to_thread(self._set_sync, key, value, expires_at)

    # ------------------------------------------------------------------
    # Sync helpers (called via asyncio.to_thread)
    # ------------------------------------------------------------------

    def _get_sync(self: SqliteCache, key: str) -> bytes | None:
        if not self._path.exists():
            return None
        with sqlite3.connect(self._path) as conn:
            conn.execute(_SCHEMA)
            row = conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        value, expires_at = row
        if expires_at <= time.time():
            return None
        return bytes(value)

    def _set_sync(self: SqliteCache, key: str, value: bytes, expires_at: float) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._path) as conn:
            conn.execute(_SCHEMA)
            conn.execute(
                "INSERT INTO cache (key, value, expires_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                "expires_at = excluded.expires_at",
                (key, value, expires_at),
            )
            conn.commit()


def get_default_cache(settings: Settings) -> CacheStore:
    """Return the process-default cache store.

    Today this always returns a :class:`SqliteCache` at
    ``evals/.cache.sqlite`` (the path required by
    ``.cursor/rules/edgar-fair-access.mdc``). The ``settings`` argument is
    reserved for the upcoming Postgres path, which will switch on
    ``settings.postgres_dsn`` reachability.
    """
    _ = settings  # reserved for the PostgresCache decision in a follow-up PR
    return SqliteCache(path=DEFAULT_CACHE_PATH)
