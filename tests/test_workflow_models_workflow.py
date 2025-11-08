"""Workflow domain model tests split from the original monolithic suite."""

from __future__ import annotations
from uuid import uuid4
import pytest
from orcheo.models import (
    Workflow,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowVersion,
    hash_publish_token,
)


def test_workflow_slug_is_derived_from_name() -> None:
    workflow = Workflow(name="My Sample Flow")

    assert workflow.slug == "my-sample-flow"
    assert workflow.audit_log == []


def test_workflow_record_event_updates_timestamp() -> None:
    workflow = Workflow(name="Demo Flow")
    original_updated_at = workflow.updated_at

    workflow.record_event(actor="alice", action="updated", metadata={"field": "name"})

    assert len(workflow.audit_log) == 1
    assert workflow.updated_at >= original_updated_at


def test_workflow_requires_name_or_slug() -> None:
    with pytest.raises(ValueError):
        Workflow(name="", slug="")


def test_workflow_tag_normalization() -> None:
    workflow = Workflow(name="Tagged", tags=["alpha", " Alpha ", "beta", ""])

    assert workflow.tags == ["alpha", "beta"]


def test_workflow_version_checksum_is_deterministic() -> None:
    graph_definition = {"nodes": [{"id": "1", "type": "start"}], "edges": []}
    version = WorkflowVersion(
        workflow_id=uuid4(),
        version=1,
        graph=graph_definition,
        created_by="alice",
    )

    checksum = version.compute_checksum()
    assert checksum == version.compute_checksum()
    version.graph["nodes"].append({"id": "2", "type": "end"})
    assert checksum != version.compute_checksum()


def test_workflow_run_state_transitions_and_audit_trail() -> None:
    run = WorkflowRun(workflow_version_id=uuid4(), triggered_by="cron")

    run.mark_started(actor="scheduler")
    assert run.status is WorkflowRunStatus.RUNNING
    assert run.started_at is not None
    assert run.audit_log[-1].action == "run_started"

    run.mark_succeeded(actor="scheduler", output={"messages": 1})
    assert run.status is WorkflowRunStatus.SUCCEEDED
    assert run.completed_at is not None
    assert run.output_payload == {"messages": 1}
    assert run.audit_log[-1].action == "run_succeeded"

    with pytest.raises(ValueError):
        run.mark_cancelled(actor="scheduler")


def test_workflow_run_invalid_transitions_raise_errors() -> None:
    run = WorkflowRun(workflow_version_id=uuid4(), triggered_by="user")

    with pytest.raises(ValueError):
        run.mark_succeeded(actor="user")

    run.mark_started(actor="user")

    with pytest.raises(ValueError):
        run.mark_started(actor="user")

    run.mark_failed(actor="user", error="boom")

    with pytest.raises(ValueError):
        run.mark_failed(actor="user", error="boom")

    with pytest.raises(ValueError):
        run.mark_cancelled(actor="user")


def test_workflow_run_cancel_records_reason() -> None:
    run = WorkflowRun(workflow_version_id=uuid4(), triggered_by="ops")
    run.mark_started(actor="ops")
    run.mark_cancelled(actor="ops", reason="manual stop")

    assert run.status is WorkflowRunStatus.CANCELLED
    assert run.error == "manual stop"
    assert run.audit_log[-1].metadata == {"reason": "manual stop"}


def test_workflow_run_cancel_without_reason() -> None:
    run = WorkflowRun(workflow_version_id=uuid4(), triggered_by="ops")
    run.mark_started(actor="ops")
    run.mark_cancelled(actor="ops")

    assert run.error is None
    assert run.audit_log[-1].metadata == {}


def test_workflow_publish_lifecycle() -> None:
    workflow = Workflow(name="Publish Demo")
    token_hash = hash_publish_token("secret-token")

    workflow.publish(token_hash=token_hash, require_login=True, actor="alice")

    assert workflow.is_public is True
    assert workflow.require_login is True
    assert workflow.publish_token_hash == token_hash
    assert workflow.published_by == "alice"
    assert workflow.published_at is not None
    assert workflow.audit_log[-1].action == "workflow_published"

    new_hash = hash_publish_token("rotated")
    workflow.rotate_publish_token(token_hash=new_hash, actor="bob")

    assert workflow.publish_token_hash == new_hash
    assert workflow.publish_token_rotated_at is not None
    assert workflow.audit_log[-1].action == "workflow_publish_token_rotated"

    workflow.revoke_publish(actor="carol")
    assert workflow.is_public is False
    assert workflow.publish_token_hash is None
    assert workflow.require_login is False
    assert workflow.published_at is None
    assert workflow.audit_log[-1].action == "workflow_unpublished"


def test_workflow_publish_invalid_transitions() -> None:
    workflow = Workflow(name="Bad Publish")
    token_hash = hash_publish_token("token")

    with pytest.raises(ValueError):
        workflow.rotate_publish_token(token_hash=token_hash, actor="alice")
    with pytest.raises(ValueError):
        workflow.revoke_publish(actor="alice")

    workflow.publish(token_hash=token_hash, require_login=False, actor="alice")

    with pytest.raises(ValueError):
        workflow.publish(token_hash=token_hash, require_login=False, actor="alice")
