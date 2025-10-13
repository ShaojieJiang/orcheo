"""End-to-end tests covering the unified trigger layer."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4
import pytest
from pydantic import ValidationError
from orcheo.triggers import (
    CronDispatchPlan,
    CronOverlapError,
    CronTriggerConfig,
    ManualDispatchItem,
    ManualDispatchPlan,
    ManualDispatchRequest,
    ManualDispatchValidationError,
    RateLimitConfig,
    RetryDecision,
    RetryPolicyConfig,
    StateCleanupConfig,
    TriggerDispatch,
    TriggerLayer,
    WebhookRequest,
    WebhookTriggerConfig,
    WebhookValidationError,
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


def test_memory_management_and_cleanup() -> None:
    """Memory management automatically cleans up expired states."""

    cleanup_config = StateCleanupConfig(
        max_retry_states=2,
        max_completed_workflows=1,
        cleanup_interval_hours=0,  # Always cleanup
        completed_workflow_ttl_hours=0,  # Immediate expiry
    )
    layer = TriggerLayer(cleanup_config)

    # Create some workflows and runs
    workflow1 = uuid4()
    workflow2 = uuid4()
    workflow3 = uuid4()

    run1 = uuid4()
    run2 = uuid4()
    run3 = uuid4()

    # Track runs to trigger cleanup logic
    layer.track_run(workflow1, run1)
    layer.track_run(workflow2, run2)

    initial_metrics = layer.get_state_metrics()
    assert initial_metrics["retry_states"] == 2
    assert initial_metrics["run_workflows"] == 2

    # Clear first run (marks workflow as completed)
    layer.clear_retry_state(run1)

    # Track third run, should trigger cleanup due to size limit
    layer.track_run(workflow3, run3)

    final_metrics = layer.get_state_metrics()
    # Should have cleaned up completed workflow due to TTL expiry
    assert final_metrics["completed_workflows"] <= 1


def test_workflow_removal() -> None:
    """Workflow removal cleans up all associated state."""

    layer = TriggerLayer()
    workflow_id = uuid4()
    run_id = uuid4()

    # Set up various states for the workflow
    layer.configure_webhook(workflow_id, WebhookTriggerConfig())
    layer.configure_cron(workflow_id, CronTriggerConfig(expression="0 9 * * *"))
    layer.configure_retry_policy(workflow_id, RetryPolicyConfig())
    layer.track_run(workflow_id, run_id)
    layer.register_cron_run(run_id)

    initial_metrics = layer.get_state_metrics()
    assert initial_metrics["webhook_states"] == 1
    assert initial_metrics["cron_states"] == 1
    assert initial_metrics["retry_configs"] == 1
    assert initial_metrics["retry_states"] == 1
    assert initial_metrics["cron_run_index"] == 1

    # Remove workflow should clean up all state
    layer.remove_workflow(workflow_id)

    final_metrics = layer.get_state_metrics()
    assert final_metrics["webhook_states"] == 0
    assert final_metrics["cron_states"] == 0
    assert final_metrics["retry_configs"] == 0
    assert final_metrics["retry_states"] == 0
    assert final_metrics["cron_run_index"] == 0
    assert final_metrics["completed_workflows"] == 1


def test_state_metrics() -> None:
    """State metrics accurately reflect current state."""

    layer = TriggerLayer()

    # Initially empty
    metrics = layer.get_state_metrics()
    assert all(count == 0 for count in metrics.values())

    # Add some state
    workflow_id = uuid4()
    run_id = uuid4()

    layer.configure_webhook(workflow_id, WebhookTriggerConfig())
    layer.configure_cron(workflow_id, CronTriggerConfig(expression="0 9 * * *"))
    layer.track_run(workflow_id, run_id)

    metrics = layer.get_state_metrics()
    assert metrics["webhook_states"] == 1
    assert metrics["cron_states"] == 1
    assert metrics["retry_states"] == 1
    assert metrics["run_workflows"] == 1


def test_error_handling_and_validation() -> None:
    """Error handling validates inputs and logs appropriately."""

    layer = TriggerLayer()
    workflow_id = uuid4()

    # Test None validation for webhook dispatch
    with pytest.raises(ValueError, match="workflow_id cannot be None"):
        layer.prepare_webhook_dispatch(
            None,
            WebhookRequest(
                method="POST",
                headers={},
                query_params={},
                payload=None,
            ),
        )

    with pytest.raises(ValueError, match="request cannot be None"):
        layer.prepare_webhook_dispatch(workflow_id, None)

    # Test None validation for cron dispatches
    with pytest.raises(ValueError, match="now parameter cannot be None"):
        layer.collect_due_cron_dispatches(now=None)

    with pytest.raises(ValueError, match="workflow_id cannot be None"):
        layer.commit_cron_dispatch(None)

    # Test None validation for manual dispatch
    with pytest.raises(ValueError, match="request cannot be None"):
        layer.prepare_manual_dispatch(None, default_workflow_version_id=uuid4())

    with pytest.raises(ValueError, match="default_workflow_version_id cannot be None"):
        layer.prepare_manual_dispatch(
            ManualDispatchRequest(
                workflow_id=workflow_id,
                actor="test",
                runs=[ManualDispatchItem()],
            ),
            default_workflow_version_id=None,
        )

    # Test None validation for retry decisions
    with pytest.raises(ValueError, match="run_id cannot be None"):
        layer.next_retry_for_run(None)


def test_malformed_configuration_handling() -> None:
    """Malformed configurations are handled gracefully."""

    layer = TriggerLayer()
    workflow_id = uuid4()

    # Test invalid webhook request (missing required headers)
    layer.configure_webhook(
        workflow_id, WebhookTriggerConfig(required_headers={"X-Auth": "secret"})
    )

    invalid_request = WebhookRequest(
        method="POST",
        headers={},  # Missing required header
        query_params={},
        payload={"test": "data"},
    )

    # Should raise validation error from the underlying webhook state
    with pytest.raises(WebhookValidationError):
        layer.prepare_webhook_dispatch(workflow_id, invalid_request)


def test_concurrent_access_patterns() -> None:
    """Concurrent operations don't corrupt state."""

    layer = TriggerLayer()
    workflow_id = uuid4()

    # Configure cron trigger
    layer.configure_cron(workflow_id, CronTriggerConfig(expression="0 9 * * *"))

    # Simulate concurrent run registration attempts
    run1 = uuid4()
    run2 = uuid4()

    layer.track_run(workflow_id, run1)
    layer.register_cron_run(run1)

    # Second run should fail due to overlap protection
    layer.track_run(workflow_id, run2)
    with pytest.raises(CronOverlapError):
        layer.register_cron_run(run2)

    # State should remain consistent
    metrics = layer.get_state_metrics()
    assert metrics["cron_run_index"] == 1
    assert metrics["retry_states"] == 2  # Both runs tracked for retry


def test_collect_due_cron_dispatches_handles_naive_datetime_and_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Cron dispatch collection normalizes naive timestamps and logs failures."""

    layer = TriggerLayer()
    workflow_id = uuid4()

    class ExplodingState:
        config = CronTriggerConfig(expression="0 0 * * *", timezone="UTC")

        def peek_due(self, *, now: datetime) -> datetime:
            raise RuntimeError("boom")

        def can_dispatch(self) -> bool:
            return True

    layer._cron_states[workflow_id] = ExplodingState()
    naive_now = datetime(2025, 1, 1, 0, 0)

    with caplog.at_level("ERROR"):
        plans = layer.collect_due_cron_dispatches(now=naive_now)

    assert plans == []
    assert any("Error checking cron dispatch" in message for message in caplog.messages)


def test_commit_cron_dispatch_logs_and_reraises_failures(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Commit failures propagate after being logged."""

    layer = TriggerLayer()
    workflow_id = uuid4()

    class FailingState:
        def consume_due(self) -> None:
            raise RuntimeError("consume failed")

    layer._cron_states[workflow_id] = FailingState()

    with caplog.at_level("ERROR"):
        with pytest.raises(RuntimeError):
            layer.commit_cron_dispatch(workflow_id)

    assert any("Failed to commit cron dispatch" in msg for msg in caplog.messages)


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


def test_next_retry_for_run_logs_and_reraises_state_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Retry state errors are logged and re-raised."""

    layer = TriggerLayer()
    run_id = uuid4()
    workflow_id = uuid4()

    class FailingRetryState:
        def next_retry(self, *, failed_at: datetime | None) -> None:
            raise RuntimeError("retry failure")

    layer._retry_states[run_id] = FailingRetryState()
    layer._run_workflows[run_id] = workflow_id

    with caplog.at_level("ERROR"):
        with pytest.raises(RuntimeError):
            layer.next_retry_for_run(run_id)

    assert any("Error computing retry decision" in msg for msg in caplog.messages)


def test_cleanup_completed_workflows_removes_expired_and_oldest(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Cleanup removes expired entries and trims excess workflows."""

    config = StateCleanupConfig(
        cleanup_interval_hours=1,
        max_retry_states=10,
        max_completed_workflows=1,
        completed_workflow_ttl_hours=1,
    )
    layer = TriggerLayer(cleanup_config=config)
    now = datetime.now(tz=UTC)
    expired_workflow = uuid4()
    recent_one = uuid4()
    recent_two = uuid4()
    layer._completed_workflows = {
        expired_workflow: now - timedelta(hours=2),
        recent_one: now - timedelta(minutes=30),
        recent_two: now - timedelta(minutes=10),
    }

    with caplog.at_level("INFO"):
        layer._cleanup_completed_workflows(now)

    assert expired_workflow not in layer._completed_workflows
    assert len(layer._completed_workflows) == 1
    assert any("Cleaned up" in msg for msg in caplog.messages)


def test_edge_cases_and_missing_state() -> None:
    """Edge cases with missing state are handled gracefully."""

    layer = TriggerLayer()

    # Operations on non-existent workflows/runs should not crash
    non_existent_workflow = uuid4()
    non_existent_run = uuid4()

    # These should not raise errors
    layer.commit_cron_dispatch(non_existent_workflow)
    layer.register_cron_run(non_existent_run)
    layer.release_cron_run(non_existent_run)
    layer.clear_retry_state(non_existent_run)

    # Should return None for missing retry state
    assert layer.next_retry_for_run(non_existent_run) is None

    # Should return default configs for non-existent workflows
    webhook_config = layer.get_webhook_config(non_existent_workflow)
    assert isinstance(webhook_config, WebhookTriggerConfig)

    cron_config = layer.get_cron_config(non_existent_workflow)
    assert isinstance(cron_config, CronTriggerConfig)

    retry_config = layer.get_retry_policy_config(non_existent_workflow)
    assert isinstance(retry_config, RetryPolicyConfig)


def test_cleanup_config_validation() -> None:
    """StateCleanupConfig provides reasonable defaults and validation."""

    # Test default config
    config = StateCleanupConfig()
    assert config.max_retry_states > 0
    assert config.max_completed_workflows > 0
    assert config.cleanup_interval_hours > 0
    assert config.completed_workflow_ttl_hours > 0

    # Test custom config
    custom_config = StateCleanupConfig(
        max_retry_states=100,
        max_completed_workflows=50,
        cleanup_interval_hours=2,
        completed_workflow_ttl_hours=48,
    )

    layer = TriggerLayer(custom_config)
    assert layer._cleanup_config.max_retry_states == 100
    assert layer._cleanup_config.max_completed_workflows == 50
    assert layer._cleanup_config.cleanup_interval_hours == 2
    assert layer._cleanup_config.completed_workflow_ttl_hours == 48
