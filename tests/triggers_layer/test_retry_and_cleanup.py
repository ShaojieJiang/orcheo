"""Trigger layer retry tracking and cleanup tests."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
from uuid import uuid4
import pytest
from orcheo.triggers import (
    CronTriggerConfig,
    RetryDecision,
    RetryPolicyConfig,
    StateCleanupConfig,
    TriggerLayer,
    WebhookTriggerConfig,
)


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

    layer.clear_retry_state(run_id)


def test_memory_management_and_cleanup() -> None:
    """Memory management automatically cleans up expired states."""

    cleanup_config = StateCleanupConfig(
        max_retry_states=2,
        max_completed_workflows=1,
        cleanup_interval_hours=0,
        completed_workflow_ttl_hours=0,
    )
    layer = TriggerLayer(cleanup_config)

    workflow1 = uuid4()
    workflow2 = uuid4()
    workflow3 = uuid4()

    run1 = uuid4()
    run2 = uuid4()
    run3 = uuid4()

    layer.track_run(workflow1, run1)
    layer.track_run(workflow2, run2)

    initial_metrics = layer.get_state_metrics()
    assert initial_metrics["retry_states"] == 2
    assert initial_metrics["run_workflows"] == 2

    layer.clear_retry_state(run1)
    layer.track_run(workflow3, run3)

    final_metrics = layer.get_state_metrics()
    assert final_metrics["completed_workflows"] <= 1


def test_workflow_removal() -> None:
    """Workflow removal cleans up all associated state."""

    layer = TriggerLayer()
    workflow_id = uuid4()
    run_id = uuid4()

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
    metrics = layer.get_state_metrics()
    assert all(count == 0 for count in metrics.values())

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
    non_existent_workflow = uuid4()
    non_existent_run = uuid4()

    layer.commit_cron_dispatch(non_existent_workflow)
    layer.register_cron_run(non_existent_run)
    layer.release_cron_run(non_existent_run)
    layer.clear_retry_state(non_existent_run)

    assert layer.next_retry_for_run(non_existent_run) is None

    webhook_config = layer.get_webhook_config(non_existent_workflow)
    assert isinstance(webhook_config, WebhookTriggerConfig)

    cron_config = layer.get_cron_config(non_existent_workflow)
    assert isinstance(cron_config, CronTriggerConfig)

    retry_config = layer.get_retry_policy_config(non_existent_workflow)
    assert isinstance(retry_config, RetryPolicyConfig)


def test_cleanup_config_validation() -> None:
    """StateCleanupConfig provides reasonable defaults and validation."""

    config = StateCleanupConfig()
    assert config.max_retry_states > 0
    assert config.max_completed_workflows > 0
    assert config.cleanup_interval_hours > 0
    assert config.completed_workflow_ttl_hours > 0

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
