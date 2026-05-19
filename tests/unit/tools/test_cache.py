"""Tests for ``mcp_financial_data.tools.cache``.

Per ADR 0006: ``CacheStore`` Protocol with a stdlib-sqlite3 backed
``SqliteCache`` implementation. Postgres is deferred to a follow-up.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_financial_data.tools.cache import (
    CacheStore,
    SqliteCache,
    get_default_cache,
)


@pytest.fixture
def cache(tmp_path: Path) -> SqliteCache:
    """Fresh SqliteCache rooted at a per-test temp file."""
    return SqliteCache(path=tmp_path / "test_cache.sqlite")


@pytest.mark.asyncio
async def test_get_returns_none_on_miss(cache: SqliteCache) -> None:
    assert await cache.get("missing-key") is None


@pytest.mark.asyncio
async def test_set_then_get_roundtrip(cache: SqliteCache) -> None:
    await cache.set("k1", b"hello world", ttl_seconds=60)
    assert await cache.get("k1") == b"hello world"


@pytest.mark.asyncio
async def test_set_overwrites_existing_key(cache: SqliteCache) -> None:
    await cache.set("k1", b"first", ttl_seconds=60)
    await cache.set("k1", b"second", ttl_seconds=60)
    assert await cache.get("k1") == b"second"


@pytest.mark.asyncio
async def test_expired_entry_returns_none(
    cache: SqliteCache, monkeypatch: pytest.MonkeyPatch
) -> None:
    await cache.set("k1", b"hello", ttl_seconds=60)
    # Advance the wall clock past the TTL.
    import time as time_mod

    real_time = time_mod.time()
    monkeypatch.setattr(time_mod, "time", lambda: real_time + 120)
    assert await cache.get("k1") is None


@pytest.mark.asyncio
async def test_rejects_non_positive_ttl(cache: SqliteCache) -> None:
    with pytest.raises(ValueError, match="ttl"):
        await cache.set("k1", b"x", ttl_seconds=-1)


@pytest.mark.asyncio
async def test_sqlite_cache_creates_parent_dirs(tmp_path: Path) -> None:
    """Cache should `mkdir -p` the parent of its sqlite path on first write."""
    deep_path = tmp_path / "a" / "b" / "c" / "cache.sqlite"
    c = SqliteCache(path=deep_path)
    await c.set("k1", b"value", ttl_seconds=60)
    assert deep_path.exists()
    assert await c.get("k1") == b"value"


@pytest.mark.asyncio
async def test_two_caches_share_disk_state(tmp_path: Path) -> None:
    """A second SqliteCache opened on the same file sees prior writes."""
    path = tmp_path / "shared.sqlite"
    a = SqliteCache(path=path)
    await a.set("k1", b"from-a", ttl_seconds=60)
    b = SqliteCache(path=path)
    assert await b.get("k1") == b"from-a"


def test_get_default_cache_returns_cachestore_at_evals_dotcache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get_default_cache(settings) returns a CacheStore rooted at the
    project's evals/.cache.sqlite per .cursor/rules/edgar-fair-access.mdc."""
    monkeypatch.chdir(tmp_path)
    from mcp_financial_data.settings import reload_settings

    settings = reload_settings()
    store = get_default_cache(settings)
    assert isinstance(store, CacheStore)
