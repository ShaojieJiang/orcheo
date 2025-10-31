"""Shared helpers for CLI commands."""

from __future__ import annotations
from collections.abc import Callable
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.state import CLIState


def load_with_cache[T](
    state: CLIState,
    cache_key: str,
    loader: Callable[[], T],
) -> tuple[T, bool, bool]:
    """Return payload using cache fallback when offline is enabled."""
    if state.settings.offline:
        entry = state.cache.load(cache_key)
        if entry is not None:
            return entry.payload, True, entry.is_stale

    try:
        payload = loader()
    except CLIError:
        entry = state.cache.load(cache_key)
        if entry is None:
            raise
        return entry.payload, True, entry.is_stale

    state.cache.store(cache_key, payload)
    return payload, False, False
