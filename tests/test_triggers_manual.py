"""Unit tests covering manual trigger dispatch helpers."""

from uuid import uuid4
import pytest
from pydantic import ValidationError
from orcheo.triggers.manual import (
    ManualDispatchItem,
    ManualDispatchRequest,
    ManualDispatchValidationError,
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
