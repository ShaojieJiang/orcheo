"""Tests for compiler helpers that build listener subscriptions."""

from __future__ import annotations
from uuid import uuid4
from orcheo.listeners.compiler import compile_listener_subscriptions
from orcheo.listeners.models import ListenerPlatform


def test_compile_listener_subscriptions_filters_invalid_entries() -> None:
    workflow_id = uuid4()
    version_id = uuid4()
    graph = {
        "index": {
            "listeners": [
                "not a dict",
                {"node_name": "", "platform": "discord"},
                {"node_name": "invalid", "platform": "unknown"},
                {
                    "node_name": "explicit",
                    "platform": "discord",
                    "bot_identity_key": "  explicit-key  ",
                    "extra": "value",
                    "type": "ignored",
                    "name": "main",
                },
            ]
        }
    }

    subscriptions = compile_listener_subscriptions(workflow_id, version_id, graph)

    assert len(subscriptions) == 1
    subscription = subscriptions[0]
    assert subscription.platform == ListenerPlatform.DISCORD
    assert subscription.bot_identity_key == "explicit-key"
    assert subscription.node_name == "explicit"
    assert subscription.config == {
        "extra": "value",
        "bot_identity_key": "  explicit-key  ",
    }


def test_compile_listener_subscriptions_derives_identity_keys() -> None:
    workflow_id = uuid4()
    version_id = uuid4()
    graph = {
        "index": {
            "listeners": [
                {
                    "node_name": "token",
                    "platform": " telegram ",
                    "token": "  tok  ",
                    "extra": "keep",
                },
                {
                    "name": "app-node",
                    "platform": "qq",
                    "app_id": "app-1",
                },
                {
                    "node_name": "credential",
                    "platform": "discord",
                    "credential_ref": " cred-1 ",
                    "payload": "info",
                },
                {
                    "node_name": "fallback",
                    "platform": "discord",
                },
            ]
        }
    }

    subscriptions = compile_listener_subscriptions(workflow_id, version_id, graph)
    nodes = {subscription.node_name: subscription for subscription in subscriptions}

    assert nodes["token"].bot_identity_key == "telegram:tok"
    assert nodes["token"].config["token"] == "  tok  "
    assert nodes["token"].config["extra"] == "keep"
    assert nodes["app-node"].bot_identity_key == "qq:app-1"
    assert nodes["credential"].bot_identity_key == "discord:cred-1"
    assert nodes["credential"].config == {
        "credential_ref": " cred-1 ",
        "payload": "info",
    }
    assert nodes["fallback"].bot_identity_key == "discord:fallback"


def test_compile_listener_subscriptions_returns_empty_for_non_listeners() -> None:
    workflow_id = uuid4()
    version_id = uuid4()
    graph = {"index": {"listeners": "invalid"}}

    assert compile_listener_subscriptions(workflow_id, version_id, graph) == []


def test_compile_listener_subscriptions_skips_empty_platform_value() -> None:
    """Entries with empty/blank platform are skipped (line 29)."""
    workflow_id = uuid4()
    version_id = uuid4()
    graph = {
        "index": {
            "listeners": [
                {"node_name": "bot", "platform": ""},
                {"node_name": "bot2"},  # no platform key at all
                {"node_name": "bot3", "platform": "   "},  # whitespace only
            ]
        }
    }

    result = compile_listener_subscriptions(workflow_id, version_id, graph)
    assert result == []
