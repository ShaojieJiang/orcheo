"""Manual trigger configuration validation tests."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
import pytest
from pydantic import ValidationError
from orcheo.triggers.manual import ManualTriggerConfig, ManualTriggerValidationError


def test_manual_trigger_config_normalizes_values() -> None:
    config = ManualTriggerConfig(
        label="  Launch  ",
        allowed_actors=["Alice", "alice", "  Bob  "],
        default_payload={"foo": "bar"},
    )

    assert config.label == "Launch"
    assert config.allowed_actors == ["Alice", "Bob"]
    assert config.default_payload == {"foo": "bar"}

    config_with_timestamp = ManualTriggerConfig(
        last_dispatched_at=datetime.now(UTC),
        cooldown_seconds=0,
    )
    assert config_with_timestamp.last_dispatched_at is not None


def test_manual_trigger_config_future_timestamp_rejected() -> None:
    future = datetime.now(UTC) + timedelta(seconds=5)
    with pytest.raises(ValidationError) as exc:
        ManualTriggerConfig(last_dispatched_at=future, cooldown_seconds=10)
    error = exc.value.errors()[0]["ctx"]["error"]
    assert isinstance(error, ManualTriggerValidationError)


def test_manual_trigger_config_empty_label_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        ManualTriggerConfig(label="   ")
    error = exc.value.errors()[0]["ctx"]["error"]
    assert isinstance(error, ManualTriggerValidationError)
    assert "label must be a non-empty string" in str(error)


def test_manual_trigger_config_empty_actors_filtered() -> None:
    config = ManualTriggerConfig(allowed_actors=["Alice", "   ", "", "Bob", "  "])
    assert config.allowed_actors == ["Alice", "Bob"]


def test_manual_trigger_config_cooldown_without_timestamp() -> None:
    config = ManualTriggerConfig(cooldown_seconds=60)
    assert config.cooldown_seconds == 60
    assert config.last_dispatched_at is None


def test_manual_trigger_config_cooldown_with_past_timestamp() -> None:
    past = datetime.now(UTC) - timedelta(seconds=30)
    config = ManualTriggerConfig(last_dispatched_at=past, cooldown_seconds=10)
    assert config.last_dispatched_at == past
    assert config.cooldown_seconds == 10


def test_manual_trigger_config_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError) as exc:
        ManualTriggerConfig(label="test", unexpected_field="value")  # type: ignore[call-arg]
    assert "unexpected_field" in str(exc.value)


def test_manual_trigger_config_defaults() -> None:
    config = ManualTriggerConfig()
    assert config.label == "manual"
    assert config.allowed_actors == []
    assert config.require_comment is False
    assert config.default_payload == {}
    assert config.cooldown_seconds == 0
    assert config.last_dispatched_at is None
