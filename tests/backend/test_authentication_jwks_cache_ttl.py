"""JWKS cache TTL behaviour tests split from the legacy suite."""

from __future__ import annotations
from datetime import UTC, datetime
import pytest
from orcheo_backend.app.authentication import JWKSCache


@pytest.mark.asyncio
async def test_jwks_cache_uses_shorter_header_ttl() -> None:
    """The JWKS cache honours a shorter Cache-Control max-age."""

    fetch_count = 0

    async def fetcher() -> tuple[list[dict[str, str]], int | None]:
        nonlocal fetch_count
        fetch_count += 1
        return ([{"kid": "key-1"}], 60)

    cache = JWKSCache(fetcher, ttl_seconds=300)

    keys = await cache.keys()

    assert keys == [{"kid": "key-1"}]
    assert fetch_count == 1
    assert cache._expires_at is not None  # noqa: SLF001 - accessed for verification only

    remaining = (cache._expires_at - datetime.now(tz=UTC)).total_seconds()
    assert remaining == pytest.approx(60, abs=1.0)


@pytest.mark.asyncio
async def test_jwks_cache_caps_ttl_to_configured_default() -> None:
    """The cache does not exceed the configured TTL when headers allow longer."""

    async def fetcher() -> tuple[list[dict[str, str]], int | None]:
        return ([{"kid": "key-1"}], 600)

    cache = JWKSCache(fetcher, ttl_seconds=120)

    await cache.keys()

    assert cache._expires_at is not None  # noqa: SLF001 - accessed for verification only
    remaining = (cache._expires_at - datetime.now(tz=UTC)).total_seconds()
    assert remaining == pytest.approx(120, abs=1.0)


@pytest.mark.asyncio
async def test_jwks_cache_refetches_when_header_disables_caching() -> None:
    """A header with max-age=0 forces the cache to refetch on every call."""

    fetch_count = 0

    async def fetcher() -> tuple[list[dict[str, str]], int | None]:
        nonlocal fetch_count
        fetch_count += 1
        return ([{"kid": "key-1"}], 0)

    cache = JWKSCache(fetcher, ttl_seconds=120)

    await cache.keys()
    assert cache._expires_at is None  # noqa: SLF001 - accessed for verification only

    await cache.keys()

    assert fetch_count == 2
