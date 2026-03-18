"""Tests for the trigger registry module."""

from __future__ import annotations
from typing import Any
import pytest
from orcheo.triggers.registry import TriggerMetadata, TriggerRegistry


def _make_registry() -> TriggerRegistry:
    return TriggerRegistry()


def test_register_and_get() -> None:
    """register stores metadata and factory; get retrieves the registration."""
    registry = _make_registry()
    metadata = TriggerMetadata(id="cron", display_name="Cron", description="Schedule")

    def factory(**kwargs: Any) -> dict[str, Any]:
        return {"kind": "cron", **kwargs}

    registry.register(metadata, factory)
    registration = registry.get("cron")

    assert registration is not None
    assert registration.metadata is metadata
    assert registration.factory is factory


def test_get_unknown_returns_none() -> None:
    """get returns None for unknown trigger ids."""
    registry = _make_registry()
    assert registry.get("unknown") is None


def test_register_duplicate_raises() -> None:
    """Registering the same id twice raises ValueError (lines 36-37)."""
    registry = _make_registry()
    meta = TriggerMetadata(id="webhook", display_name="Webhook")

    def noop() -> None:
        pass

    registry.register(meta, noop)

    with pytest.raises(ValueError, match="webhook"):
        registry.register(meta, noop)


def test_list_metadata_empty() -> None:
    """list_metadata returns an empty list when no triggers are registered."""
    registry = _make_registry()
    assert registry.list_metadata() == []


def test_list_metadata_sorted() -> None:
    """list_metadata returns entries sorted by id case-insensitively (line 49)."""
    registry = _make_registry()

    def noop() -> None:
        pass

    registry.register(TriggerMetadata(id="webhook", display_name="Webhook"), noop)
    registry.register(TriggerMetadata(id="Cron", display_name="Cron"), noop)
    registry.register(TriggerMetadata(id="manual", display_name="Manual"), noop)

    ids = [m.id for m in registry.list_metadata()]
    assert ids == ["Cron", "manual", "webhook"]


def test_unregister_removes_registration() -> None:
    """unregister removes an existing trigger registration."""
    registry = _make_registry()

    def noop() -> None:
        pass

    registry.register(TriggerMetadata(id="cron", display_name="Cron"), noop)
    registry.unregister("cron")
    assert registry.get("cron") is None


def test_unregister_unknown_is_noop() -> None:
    """unregister silently ignores unknown ids."""
    registry = _make_registry()
    registry.unregister("does-not-exist")  # should not raise
