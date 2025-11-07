"""Trigger layer manual dispatch tests."""

from __future__ import annotations
from uuid import UUID, uuid4
import pytest
from pydantic import ValidationError
from orcheo.triggers import (
    ManualDispatchItem,
    ManualDispatchPlan,
    ManualDispatchRequest,
    ManualDispatchValidationError,
    TriggerLayer,
)


def test_manual_dispatch_plan_resolution() -> None:
    """Manual dispatch plans normalise actor, label, and run payloads."""

    workflow_id = uuid4()
    default_version = uuid4()
    layer = TriggerLayer()

    with pytest.raises(ValidationError):
        ManualDispatchRequest(workflow_id=workflow_id, actor=" ", runs=[])

    explicit_version = uuid4()
    request = ManualDispatchRequest(
        workflow_id=workflow_id,
        actor="  ops  ",
        runs=[
            ManualDispatchItem(input_payload={"foo": "bar"}),
            ManualDispatchItem(
                workflow_version_id=explicit_version,
                input_payload={"baz": 1},
            ),
        ],
    )

    plan = layer.prepare_manual_dispatch(
        request, default_workflow_version_id=default_version
    )
    assert isinstance(plan, ManualDispatchPlan)
    assert plan.actor == "ops"
    assert plan.triggered_by == "manual_batch"
    assert plan.runs[0].workflow_version_id == default_version
    assert plan.runs[1].workflow_version_id == explicit_version


def test_prepare_manual_dispatch_logs_and_reraises_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Manual dispatch preparation surfaces resolution failures."""

    layer = TriggerLayer()
    default_version_id = uuid4()

    class BrokenRequest:
        actor = "manual"

        def trigger_label(self) -> str:
            return "manual"

        def resolve_runs(self, *, default_workflow_version_id: UUID) -> None:
            raise ManualDispatchValidationError("broken request")

    request = BrokenRequest()

    with caplog.at_level("ERROR"):
        with pytest.raises(ManualDispatchValidationError):
            layer.prepare_manual_dispatch(
                request, default_workflow_version_id=default_version_id
            )

    assert any("Failed to prepare manual dispatch" in msg for msg in caplog.messages)
