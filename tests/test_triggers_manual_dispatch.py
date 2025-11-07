"""Manual dispatch request and item validation tests."""

from __future__ import annotations
from uuid import uuid4
import pytest
from pydantic import ValidationError
from orcheo.triggers.manual import (
    ManualDispatchItem,
    ManualDispatchRequest,
    ManualDispatchRun,
    ManualDispatchValidationError,
)


def test_manual_dispatch_trigger_label_defaults() -> None:
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
    request = ManualDispatchRequest(
        workflow_id=uuid4(),
        actor="operator",
        runs=[ManualDispatchItem()],
        label="manual_debug",
    )
    assert request.trigger_label() == "manual_debug"


def test_manual_dispatch_resolve_runs_applies_defaults() -> None:
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


def test_manual_dispatch_item_defaults() -> None:
    item = ManualDispatchItem()
    assert item.workflow_version_id is None
    assert item.input_payload == {}


def test_manual_dispatch_item_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError) as exc:
        ManualDispatchItem(extra_field="value")  # type: ignore[call-arg]
    assert "extra_field" in str(exc.value)


def test_manual_dispatch_request_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError) as exc:
        ManualDispatchRequest(  # type: ignore[call-arg]
            workflow_id=uuid4(),
            actor="operator",
            runs=[ManualDispatchItem()],
            extra_field="value",
        )
    assert "extra_field" in str(exc.value)


def test_manual_dispatch_resolve_runs_with_explicit_version() -> None:
    default_version = uuid4()
    explicit_version = uuid4()

    request = ManualDispatchRequest(
        workflow_id=uuid4(),
        actor="operator",
        runs=[
            ManualDispatchItem(workflow_version_id=explicit_version),
            ManualDispatchItem(),
        ],
    )

    resolved = request.resolve_runs(default_workflow_version_id=default_version)
    assert len(resolved) == 2
    assert resolved[0].workflow_version_id == explicit_version
    assert resolved[1].workflow_version_id == default_version


def test_manual_dispatch_resolve_runs_copies_payload() -> None:
    request = ManualDispatchRequest(
        workflow_id=uuid4(),
        actor="operator",
        runs=[ManualDispatchItem(input_payload={"key": "value"})],
    )

    resolved = request.resolve_runs(default_workflow_version_id=uuid4())
    assert resolved[0].input_payload == {"key": "value"}
    resolved[0].input_payload["key"] = "modified"
    assert request.runs[0].input_payload["key"] == "value"


def test_manual_dispatch_request_max_runs_limit() -> None:
    request = ManualDispatchRequest(
        workflow_id=uuid4(),
        actor="operator",
        runs=[ManualDispatchItem() for _ in range(100)],
    )
    assert len(request.runs) == 100

    with pytest.raises(ValidationError) as exc:
        ManualDispatchRequest(
            workflow_id=uuid4(),
            actor="operator",
            runs=[ManualDispatchItem() for _ in range(101)],
        )
    assert "at most 100 items" in exc.value.errors()[0]["msg"]


def test_manual_dispatch_run_dataclass() -> None:
    version_id = uuid4()
    payload = {"foo": "bar", "baz": 123}

    run = ManualDispatchRun(
        workflow_version_id=version_id,
        input_payload=payload,
    )

    assert run.workflow_version_id == version_id
    assert run.input_payload == payload


def test_manual_dispatch_request_defaults() -> None:
    request = ManualDispatchRequest(
        workflow_id=uuid4(),
        runs=[ManualDispatchItem()],
    )
    assert request.actor == "manual"
    assert request.label is None
