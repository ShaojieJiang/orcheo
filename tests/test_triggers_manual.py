"""Unit tests covering manual trigger dispatch helpers."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4
import pytest
from pydantic import ValidationError
from orcheo.triggers.manual import (
    ManualDispatchItem,
    ManualDispatchRequest,
    ManualDispatchValidationError,
    ManualTriggerConfig,
    ManualTriggerValidationError,
)


def test_manual_dispatch_trigger_label_defaults() -> None:
    """Trigger label derives from run count when not provided."""

    single = ManualDispatchRequest(
        workflow_id=uuid4(),
        actor="operator",
        runs=[ManualDispatchItem()],
    )
    assert single.trigger_label() == "manual"

    batch = ManualDispatchRequest(
        workflow_id=uuid4(),
        actor="operator",
        runs=[ManualDispatchItem(), ManualDispatchItem()],
    )
    assert batch.trigger_label() == "manual_batch"

    none_label = ManualDispatchRequest(
        workflow_id=uuid4(),
        actor="operator",
        runs=[ManualDispatchItem()],
        label=None,
    )
    assert none_label.label is None


def test_manual_dispatch_trigger_label_override() -> None:
    """Explicit labels take precedence over inferred ones."""

    request = ManualDispatchRequest(
        workflow_id=uuid4(),
        actor="operator",
        runs=[ManualDispatchItem()],
        label="manual_debug",
    )
    assert request.trigger_label() == "manual_debug"


def test_manual_dispatch_resolve_runs_applies_defaults() -> None:
    """Run resolution applies the provided default version identifier."""

    workflow_version = uuid4()
    request = ManualDispatchRequest(
        workflow_id=uuid4(),
        actor="operator",
        runs=[ManualDispatchItem(input_payload={"foo": "bar"})],
    )

    resolved = request.resolve_runs(default_workflow_version_id=workflow_version)
    assert len(resolved) == 1
    assert resolved[0].workflow_version_id == workflow_version
    assert resolved[0].input_payload == {"foo": "bar"}


def test_manual_dispatch_validators_enforce_non_empty_values() -> None:
    """Validators trim values and reject empty actors or labels."""

    request = ManualDispatchRequest(
        workflow_id=uuid4(),
        actor="  operator  ",
        runs=[ManualDispatchItem()],
        label="  custom  ",
    )
    assert request.actor == "operator"
    assert request.label == "custom"

    with pytest.raises(ValidationError) as actor_exc:
        ManualDispatchRequest(
            workflow_id=uuid4(),
            actor="   ",
            runs=[ManualDispatchItem()],
        )
    assert "actor must be a non-empty string" in actor_exc.value.errors()[0]["msg"]

    with pytest.raises(ValidationError) as label_exc:
        ManualDispatchRequest(
            workflow_id=uuid4(),
            actor="operator",
            runs=[ManualDispatchItem()],
            label="   ",
        )
    assert "label must not be empty when provided" in label_exc.value.errors()[0]["msg"]

    with pytest.raises(ValidationError) as runs_exc:
        ManualDispatchRequest(
            workflow_id=uuid4(),
            actor="operator",
            runs=[],
            label=None,
        )
    assert "at least 1 item" in runs_exc.value.errors()[0]["msg"]

    manual = ManualDispatchRequest.model_construct(
        workflow_id=uuid4(),
        actor="operator",
        runs=[],
        label=None,
    )
    with pytest.raises(ManualDispatchValidationError):
        manual._enforce_run_limit()


def test_manual_trigger_config_normalizes_values() -> None:
    """Manual trigger config trims labels and deduplicates actors."""

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
    """Cooldown validation rejects future dispatch timestamps."""

    future = datetime.now(UTC) + timedelta(seconds=5)
    with pytest.raises(ValidationError) as exc:
        ManualTriggerConfig(last_dispatched_at=future, cooldown_seconds=10)
    error = exc.value.errors()[0]["ctx"]["error"]
    assert isinstance(error, ManualTriggerValidationError)


def test_manual_trigger_config_empty_label_rejected() -> None:
    """Empty labels (after stripping whitespace) are rejected."""

    with pytest.raises(ValidationError) as exc:
        ManualTriggerConfig(label="   ")
    error = exc.value.errors()[0]["ctx"]["error"]
    assert isinstance(error, ManualTriggerValidationError)
    assert "label must be a non-empty string" in str(error)


def test_manual_trigger_config_empty_actors_filtered() -> None:
    """Empty actor strings are filtered out during normalization."""

    config = ManualTriggerConfig(allowed_actors=["Alice", "   ", "", "Bob", "  "])
    assert config.allowed_actors == ["Alice", "Bob"]


def test_manual_trigger_config_cooldown_without_timestamp() -> None:
    """Cooldown validation passes when last_dispatched_at is None."""

    config = ManualTriggerConfig(cooldown_seconds=60)
    assert config.cooldown_seconds == 60
    assert config.last_dispatched_at is None


def test_manual_trigger_config_cooldown_with_past_timestamp() -> None:
    """Cooldown validation passes when last_dispatched_at is in the past."""

    past = datetime.now(UTC) - timedelta(seconds=30)
    config = ManualTriggerConfig(last_dispatched_at=past, cooldown_seconds=10)
    assert config.last_dispatched_at == past
    assert config.cooldown_seconds == 10


def test_manual_trigger_config_extra_fields_forbidden() -> None:
    """Extra fields in ManualTriggerConfig are rejected."""

    with pytest.raises(ValidationError) as exc:
        ManualTriggerConfig(label="test", unexpected_field="value")  # type: ignore[call-arg]
    assert "unexpected_field" in str(exc.value)


def test_manual_dispatch_item_defaults() -> None:
    """ManualDispatchItem has sensible defaults."""

    item = ManualDispatchItem()
    assert item.workflow_version_id is None
    assert item.input_payload == {}


def test_manual_dispatch_item_extra_fields_forbidden() -> None:
    """Extra fields in ManualDispatchItem are rejected."""

    with pytest.raises(ValidationError) as exc:
        ManualDispatchItem(extra_field="value")  # type: ignore[call-arg]
    assert "extra_field" in str(exc.value)


def test_manual_dispatch_request_extra_fields_forbidden() -> None:
    """Extra fields in ManualDispatchRequest are rejected."""

    with pytest.raises(ValidationError) as exc:
        ManualDispatchRequest(  # type: ignore[call-arg]
            workflow_id=uuid4(),
            actor="operator",
            runs=[ManualDispatchItem()],
            extra_field="value",
        )
    assert "extra_field" in str(exc.value)


def test_manual_dispatch_resolve_runs_with_explicit_version() -> None:
    """Run resolution uses explicit version when provided."""

    default_version = uuid4()
    explicit_version = uuid4()

    request = ManualDispatchRequest(
        workflow_id=uuid4(),
        actor="operator",
        runs=[
            ManualDispatchItem(workflow_version_id=explicit_version),
            ManualDispatchItem(),  # Uses default
        ],
    )

    resolved = request.resolve_runs(default_workflow_version_id=default_version)
    assert len(resolved) == 2
    assert resolved[0].workflow_version_id == explicit_version
    assert resolved[1].workflow_version_id == default_version


def test_manual_dispatch_resolve_runs_copies_payload() -> None:
    """Run resolution creates independent copies of input payloads."""

    request = ManualDispatchRequest(
        workflow_id=uuid4(),
        actor="operator",
        runs=[ManualDispatchItem(input_payload={"key": "value"})],
    )

    resolved = request.resolve_runs(default_workflow_version_id=uuid4())
    assert resolved[0].input_payload == {"key": "value"}
    # Verify it's a copy, not a reference
    resolved[0].input_payload["key"] = "modified"
    assert request.runs[0].input_payload["key"] == "value"


def test_manual_dispatch_request_max_runs_limit() -> None:
    """ManualDispatchRequest enforces maximum of 100 runs."""

    # Should succeed with 100 runs
    request = ManualDispatchRequest(
        workflow_id=uuid4(),
        actor="operator",
        runs=[ManualDispatchItem() for _ in range(100)],
    )
    assert len(request.runs) == 100

    # Should fail with 101 runs
    with pytest.raises(ValidationError) as exc:
        ManualDispatchRequest(
            workflow_id=uuid4(),
            actor="operator",
            runs=[ManualDispatchItem() for _ in range(101)],
        )
    assert "at most 100 items" in exc.value.errors()[0]["msg"]


def test_manual_dispatch_run_dataclass() -> None:
    """ManualDispatchRun dataclass correctly stores values."""
    from orcheo.triggers.manual import ManualDispatchRun

    version_id = uuid4()
    payload = {"foo": "bar", "baz": 123}

    run = ManualDispatchRun(
        workflow_version_id=version_id,
        input_payload=payload,
    )

    assert run.workflow_version_id == version_id
    assert run.input_payload == payload


def test_manual_trigger_config_defaults() -> None:
    """ManualTriggerConfig has sensible defaults."""

    config = ManualTriggerConfig()
    assert config.label == "manual"
    assert config.allowed_actors == []
    assert config.require_comment is False
    assert config.default_payload == {}
    assert config.cooldown_seconds == 0
    assert config.last_dispatched_at is None


def test_manual_dispatch_request_defaults() -> None:
    """ManualDispatchRequest has correct defaults."""

    request = ManualDispatchRequest(
        workflow_id=uuid4(),
        runs=[ManualDispatchItem()],
    )
    assert request.actor == "manual"
    assert request.label is None
