"""Tests for the listener registry module."""

from __future__ import annotations
from typing import Any
from uuid import UUID, uuid4
import pytest
from orcheo.listeners.models import ListenerSubscription
from orcheo.listeners.registry import (
    ListenerMetadata,
    ListenerRegistry,
    _derive_bot_identity_key,
    default_listener_compiler,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry() -> ListenerRegistry:
    return ListenerRegistry()


def _noop_compiler(
    *,
    workflow_id: UUID,
    workflow_version_id: UUID,
    item: dict[str, Any],
    platform_id: str,
) -> ListenerSubscription | None:
    return None


def _noop_adapter_factory(
    *,
    repository: Any,
    subscription: ListenerSubscription,
    runtime_id: str,
) -> Any:
    return object()


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


def test_register_and_resolve() -> None:
    """register stores platform; resolve retrieves it."""
    registry = _make_registry()
    meta = ListenerMetadata(id="slack", display_name="Slack")
    registry.register(
        meta, compiler=_noop_compiler, adapter_factory=_noop_adapter_factory
    )

    registration = registry.resolve("slack")
    assert registration is not None
    assert registration.metadata is meta


def test_register_duplicate_raises() -> None:
    """Registering the same platform id twice raises ValueError (lines 79-80)."""
    registry = _make_registry()
    meta = ListenerMetadata(id="dup", display_name="Dup")
    registry.register(
        meta, compiler=_noop_compiler, adapter_factory=_noop_adapter_factory
    )

    with pytest.raises(ValueError, match="dup"):
        registry.register(
            meta, compiler=_noop_compiler, adapter_factory=_noop_adapter_factory
        )


def test_register_duplicate_alias_raises() -> None:
    """Registering an alias that conflicts with existing entries raises ValueError."""
    registry = _make_registry()
    meta1 = ListenerMetadata(id="platform-a", display_name="A")
    registry.register(
        meta1,
        compiler=_noop_compiler,
        adapter_factory=_noop_adapter_factory,
        aliases=("alias-a",),
    )
    meta2 = ListenerMetadata(id="platform-b", display_name="B")
    with pytest.raises(ValueError, match="alias-a"):
        registry.register(
            meta2,
            compiler=_noop_compiler,
            adapter_factory=_noop_adapter_factory,
            aliases=("alias-a",),
        )


def test_register_with_aliases() -> None:
    """Aliases resolve to the canonical platform."""
    registry = _make_registry()
    meta = ListenerMetadata(id="telegram", display_name="Telegram")
    registry.register(
        meta,
        compiler=_noop_compiler,
        adapter_factory=_noop_adapter_factory,
        aliases=("tg", "tlg"),
    )

    assert registry.resolve("tg") is registry.resolve("telegram")
    assert registry.resolve("tlg") is registry.resolve("telegram")


# ---------------------------------------------------------------------------
# resolve
# ---------------------------------------------------------------------------


def test_resolve_unknown_returns_none() -> None:
    """resolve returns None for unknown platform ids."""
    registry = _make_registry()
    assert registry.resolve("unknown") is None


# ---------------------------------------------------------------------------
# list_metadata
# ---------------------------------------------------------------------------


def test_list_metadata_empty_registry() -> None:
    """list_metadata returns [] for empty registry (line 101)."""
    registry = _make_registry()
    assert registry.list_metadata() == []


def test_list_metadata_sorted() -> None:
    """list_metadata returns metadata sorted by id."""
    registry = _make_registry()
    registry.register(
        ListenerMetadata(id="Zoom", display_name="Zoom"),
        compiler=_noop_compiler,
        adapter_factory=_noop_adapter_factory,
    )
    registry.register(
        ListenerMetadata(id="slack", display_name="Slack"),
        compiler=_noop_compiler,
        adapter_factory=_noop_adapter_factory,
    )

    ids = [m.id for m in registry.list_metadata()]
    assert ids == ["slack", "Zoom"]


# ---------------------------------------------------------------------------
# compile_subscription
# ---------------------------------------------------------------------------


def test_compile_subscription_unknown_platform_returns_none() -> None:
    """compile_subscription returns None for unknown platform."""
    registry = _make_registry()
    result = registry.compile_subscription(
        workflow_id=uuid4(),
        workflow_version_id=uuid4(),
        item={"node_name": "bot"},
        platform_id="unknown",
    )
    assert result is None


def test_compile_subscription_calls_compiler() -> None:
    """compile_subscription delegates to the registered compiler."""
    registry = _make_registry()
    wf_id = uuid4()
    ver_id = uuid4()
    received: list[dict[str, Any]] = []

    def recording_compiler(
        *,
        workflow_id: UUID,
        workflow_version_id: UUID,
        item: dict[str, Any],
        platform_id: str,
    ) -> ListenerSubscription | None:
        received.append({"platform_id": platform_id, "item": item})
        return None

    registry.register(
        ListenerMetadata(id="myplatform", display_name="My"),
        compiler=recording_compiler,
        adapter_factory=_noop_adapter_factory,
    )
    registry.compile_subscription(
        workflow_id=wf_id,
        workflow_version_id=ver_id,
        item={"node_name": "foo"},
        platform_id="myplatform",
    )
    assert len(received) == 1
    assert received[0]["platform_id"] == "myplatform"


# ---------------------------------------------------------------------------
# build_adapter
# ---------------------------------------------------------------------------


def test_build_adapter_unknown_platform_raises() -> None:
    """build_adapter raises ValueError for unknown platform."""
    registry = _make_registry()
    sub = ListenerSubscription(
        workflow_id=uuid4(),
        workflow_version_id=uuid4(),
        node_name="n",
        platform="unknown",
        bot_identity_key="k",
    )
    with pytest.raises(ValueError, match="unknown"):
        registry.build_adapter(
            "unknown", repository=None, subscription=sub, runtime_id="rt"
        )


def test_build_adapter_calls_factory() -> None:
    """build_adapter delegates to the registered adapter factory."""
    registry = _make_registry()
    sentinel = object()

    def factory(*, repository: Any, subscription: Any, runtime_id: str) -> Any:
        return sentinel

    registry.register(
        ListenerMetadata(id="testplatform", display_name="Test"),
        compiler=_noop_compiler,
        adapter_factory=factory,
    )
    sub = ListenerSubscription(
        workflow_id=uuid4(),
        workflow_version_id=uuid4(),
        node_name="n",
        platform="testplatform",
        bot_identity_key="k",
    )
    result = registry.build_adapter(
        "testplatform", repository=None, subscription=sub, runtime_id="rt"
    )
    assert result is sentinel


# ---------------------------------------------------------------------------
# unregister
# ---------------------------------------------------------------------------


def test_unregister_removes_platform() -> None:
    """unregister removes a registered platform."""
    registry = _make_registry()
    registry.register(
        ListenerMetadata(id="temp", display_name="Temp"),
        compiler=_noop_compiler,
        adapter_factory=_noop_adapter_factory,
    )
    registry.unregister("temp")
    assert registry.resolve("temp") is None


def test_unregister_removes_aliases() -> None:
    """unregister also removes aliases pointing to the platform (line 157)."""
    registry = _make_registry()
    registry.register(
        ListenerMetadata(id="platform", display_name="Platform"),
        compiler=_noop_compiler,
        adapter_factory=_noop_adapter_factory,
        aliases=("alias1", "alias2"),
    )
    registry.unregister("platform")
    assert registry.resolve("platform") is None
    assert registry.resolve("alias1") is None
    assert registry.resolve("alias2") is None


def test_unregister_unknown_is_noop() -> None:
    """unregister silently ignores unknown platform ids (line 148)."""
    registry = _make_registry()
    registry.unregister("does-not-exist")  # should not raise


def test_unregister_via_alias() -> None:
    """unregister also works when called with an alias name."""
    registry = _make_registry()
    registry.register(
        ListenerMetadata(id="canonical", display_name="Canonical"),
        compiler=_noop_compiler,
        adapter_factory=_noop_adapter_factory,
        aliases=("old-name",),
    )
    registry.unregister("old-name")
    assert registry.resolve("canonical") is None
    assert registry.resolve("old-name") is None


# ---------------------------------------------------------------------------
# _derive_bot_identity_key
# ---------------------------------------------------------------------------


def test_derive_bot_identity_key_explicit() -> None:
    """Explicit bot_identity_key takes precedence."""
    key = _derive_bot_identity_key("telegram", {"bot_identity_key": "  my-key  "})
    assert key == "my-key"


def test_derive_bot_identity_key_from_token() -> None:
    """Falls back to token field."""
    key = _derive_bot_identity_key("telegram", {"token": "  abc123  "})
    assert key == "telegram:abc123"


def test_derive_bot_identity_key_from_app_id() -> None:
    """Falls back to app_id field."""
    key = _derive_bot_identity_key("lark", {"app_id": "la_123"})
    assert key == "lark:la_123"


def test_derive_bot_identity_key_from_credential_ref() -> None:
    """Falls back to credential_ref field."""
    key = _derive_bot_identity_key("discord", {"credential_ref": "discord-cred"})
    assert key == "discord:discord-cred"


def test_derive_bot_identity_key_fallback_to_node_name() -> None:
    """Falls back to node_name or name when no key fields present."""
    key = _derive_bot_identity_key("discord", {"node_name": "my-bot"})
    assert key == "discord:my-bot"


# ---------------------------------------------------------------------------
# default_listener_compiler
# ---------------------------------------------------------------------------


def test_default_listener_compiler_empty_node_name_returns_none() -> None:
    """Returns None when node_name is empty or missing."""
    result = default_listener_compiler(
        workflow_id=uuid4(),
        workflow_version_id=uuid4(),
        item={"node_name": ""},
        platform_id="telegram",
    )
    assert result is None


def test_default_listener_compiler_creates_subscription() -> None:
    """Creates a valid subscription from a well-formed item."""
    wf_id = uuid4()
    ver_id = uuid4()
    result = default_listener_compiler(
        workflow_id=wf_id,
        workflow_version_id=ver_id,
        item={"node_name": "bot", "token": "tok", "extra": "val", "type": "ignored"},
        platform_id="telegram",
    )
    assert result is not None
    assert result.workflow_id == wf_id
    assert result.node_name == "bot"
    assert result.platform == "telegram"
    assert "extra" in result.config
    assert "type" not in result.config
