"""Unit tests for trigger retry policy helpers."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
from random import Random
import pytest
from orcheo.triggers import (
    RetryDecision,
    RetryPolicyConfig,
    RetryPolicyState,
    RetryPolicyValidationError,
)


def test_retry_policy_state_produces_bounded_schedule() -> None:
    """Retry decisions should honour max attempts and backoff configuration."""

    config = RetryPolicyConfig(
        max_attempts=3,
        initial_delay_seconds=10.0,
        backoff_factor=2.0,
        max_delay_seconds=25.0,
        jitter_factor=0.0,
    )
    state = RetryPolicyState(config)
    failure_time = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)

    config_clone = state.config
    assert config_clone is not config
    assert config_clone == config

    first = state.next_retry(failed_at=failure_time)
    assert isinstance(first, RetryDecision)
    assert first.retry_number == 1
    assert first.delay_seconds == pytest.approx(10.0)
    assert first.scheduled_for == failure_time + timedelta(seconds=10)
    assert state.remaining_attempts == 1

    second = state.next_retry(failed_at=failure_time)
    assert second is not None
    assert second.retry_number == 2
    assert second.delay_seconds == pytest.approx(20.0)
    assert second.scheduled_for == failure_time + timedelta(seconds=20)
    assert state.remaining_attempts == 0

    assert state.next_retry(failed_at=failure_time) is None


def test_retry_policy_state_reset_allows_new_sequence() -> None:
    """Resetting the state should make retries available again."""

    state = RetryPolicyState(
        RetryPolicyConfig(max_attempts=2, initial_delay_seconds=5.0, jitter_factor=0.0)
    )
    state.next_retry(failed_at=datetime.now(tz=UTC))
    assert state.remaining_attempts == 0

    state.reset()
    assert state.remaining_attempts == 1


def test_retry_policy_applies_deterministic_jitter() -> None:
    """Providing a seeded RNG should yield deterministic jittered delays."""

    config = RetryPolicyConfig(
        max_attempts=2,
        initial_delay_seconds=8.0,
        jitter_factor=0.5,
    )
    state = RetryPolicyState(config, random_state=Random(7))
    decision = state.next_retry(failed_at=datetime(2024, 5, 10, 12, tzinfo=UTC))
    assert decision is not None
    assert decision.delay_seconds == pytest.approx(6.590662118665299, rel=1e-9)
    assert decision.scheduled_for.isoformat() == "2024-05-10T12:00:06.590662+00:00"


def test_retry_policy_config_rejects_negative_attempt_index() -> None:
    """Computing delays with a negative attempt index should fail."""

    config = RetryPolicyConfig(initial_delay_seconds=1.0, jitter_factor=0.0)
    with pytest.raises(RetryPolicyValidationError):
        config.compute_delay_seconds(attempt_index=-1)


def test_retry_policy_without_delay_cap() -> None:
    """Policies without a delay cap should honour exponential backoff."""

    config = RetryPolicyConfig(
        max_attempts=3,
        initial_delay_seconds=2.0,
        backoff_factor=3.0,
        max_delay_seconds=None,
        jitter_factor=0.0,
    )
    state = RetryPolicyState(config)
    failure_time = datetime(2024, 6, 1, 0, 0, tzinfo=UTC)

    first = state.next_retry(failed_at=failure_time)
    assert first is not None
    assert first.delay_seconds == pytest.approx(2.0)
    second = state.next_retry(failed_at=failure_time)
    assert second is not None
    assert second.delay_seconds == pytest.approx(6.0)
