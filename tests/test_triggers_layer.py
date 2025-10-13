"""End-to-end tests covering the unified trigger layer."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from orcheo.triggers import (
    CronDispatchPlan,
    CronOverlapError,
    CronTriggerConfig,
    ManualDispatchItem,
    ManualDispatchPlan,
    ManualDispatchRequest,
    RateLimitConfig,
    RetryDecision,
    RetryPolicyConfig,
    TriggerDispatch,
    TriggerLayer,
    WebhookRequest,
    WebhookTriggerConfig,
)


def test_webhook_dispatch_validation_and_normalization() -> None:
    """Webhook dispatch plans include normalized payload and metadata."""

    workflow_id = uuid4()
    layer = TriggerLayer()

    config = WebhookTriggerConfig(
        allowed_methods=["post"],
        required_headers={"X-Auth": "secret"},
        required_query_params={"team": "ops"},
        rate_limit=RateLimitConfig(limit=10, interval_seconds=60),
    )
    stored = layer.configure_webhook(workflow_id, config)
    assert stored.allowed_methods == ["POST"]

    request = WebhookRequest(
        method="POST",
        headers={"X-Auth": "secret"},
        query_params={"team": "ops"},
        payload={"key": "value"},
        source_ip="203.0.113.5",
    )

    dispatch = layer.prepare_webhook_dispatch(workflow_id, request)
    assert isinstance(dispatch, TriggerDispatch)
    assert dispatch.triggered_by == "webhook"
    assert dispatch.actor == "webhook"
    assert dispatch.input_payload["headers"]["x-auth"] == "secret"
    assert dispatch.input_payload["query_params"] == {"team": "ops"}
    assert dispatch.input_payload["source_ip"] == "203.0.113.5"


def test_cron_dispatch_and_overlap_controls() -> None:
    """Cron dispatch plans honour timezone and overlap guards."""

    workflow_id = uuid4()
    layer = TriggerLayer()
    layer.configure_cron(
        workflow_id,
        CronTriggerConfig(expression="0 9 * * *", timezone="UTC"),
    )

    reference = datetime(2025, 1, 1, 9, 0, tzinfo=UTC)
    plans = layer.collect_due_cron_dispatches(now=reference)
    assert plans == [
        CronDispatchPlan(
            workflow_id=workflow_id,
            scheduled_for=reference,
            timezone="UTC",
        )
    ]

    # Cron occurrences remain pending until they are explicitly committed.
    repeat_plans = layer.collect_due_cron_dispatches(now=reference)
    assert repeat_plans == plans

    run_id = uuid4()
    layer.track_run(workflow_id, run_id)
    layer.register_cron_run(run_id)

    with pytest.raises(CronOverlapError):
        conflicting_run = uuid4()
        layer.track_run(workflow_id, conflicting_run)
        layer.register_cron_run(conflicting_run)

    layer.commit_cron_dispatch(workflow_id)
    layer.release_cron_run(run_id)
    next_plans = layer.collect_due_cron_dispatches(
        now=datetime(2025, 1, 2, 9, 0, tzinfo=UTC)
    )
    assert next_plans[0].timezone == "UTC"


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


def test_retry_policy_decisions_are_tracked_per_run() -> None:
    """Retry decisions honour configured policy and clear exhausted state."""

    workflow_id = uuid4()
    layer = TriggerLayer()

    config = RetryPolicyConfig(
        max_attempts=2,
        initial_delay_seconds=5.0,
        jitter_factor=0.0,
    )
    layer.configure_retry_policy(workflow_id, config)
    stored = layer.get_retry_policy_config(workflow_id)
    assert stored.max_attempts == 2

    run_id = uuid4()
    layer.track_run(workflow_id, run_id)

    first = layer.next_retry_for_run(
        run_id, failed_at=datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    )
    assert isinstance(first, RetryDecision)
    assert first.retry_number == 1
    assert pytest.approx(first.delay_seconds) == 5.0

    exhausted = layer.next_retry_for_run(
        run_id, failed_at=datetime(2025, 1, 1, 12, 5, tzinfo=UTC)
    )
    assert exhausted is None

    # Additional cleanup should be idempotent once retries are exhausted.
    layer.clear_retry_state(run_id)
