from __future__ import annotations
from datetime import UTC, datetime
from uuid import uuid4
import pytest
from pydantic import ValidationError
from orcheo.triggers.cron import (
    CronOverlapError,
    CronTriggerConfig,
    CronTriggerState,
    CronValidationError,
)


def test_cron_trigger_state_computes_next_occurrence() -> None:
    """Cron trigger state should surface the next due time and advance."""

    config = CronTriggerConfig(expression="0 9 * * *", timezone="UTC")
    state = CronTriggerState(config)

    first_due = state.peek_due(now=datetime(2025, 1, 1, 9, 0, tzinfo=UTC))
    assert first_due == datetime(2025, 1, 1, 9, 0, tzinfo=UTC)

    consumed = state.consume_due()
    assert consumed == first_due

    assert state.peek_due(now=datetime(2025, 1, 1, 9, 5, tzinfo=UTC)) is None

    next_due = state.peek_due(now=datetime(2025, 1, 2, 9, 0, tzinfo=UTC))
    assert next_due == datetime(2025, 1, 2, 9, 0, tzinfo=UTC)


def test_cron_trigger_respects_timezone() -> None:
    """Schedules should be evaluated according to the configured timezone."""

    config = CronTriggerConfig(expression="30 9 * * *", timezone="America/New_York")
    state = CronTriggerState(config)

    reference = datetime(2025, 1, 1, 14, 30, tzinfo=UTC)
    due = state.peek_due(now=reference)
    assert due == reference


def test_cron_trigger_overlap_guard() -> None:
    """Overlap protection prevents multiple pending runs."""

    config = CronTriggerConfig(expression="0 * * * *", allow_overlapping=False)
    state = CronTriggerState(config)

    now = datetime(2025, 1, 1, 0, 0, tzinfo=UTC)
    assert state.peek_due(now=now) is not None

    run_id = uuid4()
    state.register_run(run_id)
    assert state.can_dispatch() is False

    state.release_run(run_id)
    assert state.can_dispatch() is True


def test_cron_trigger_overlap_guard_raises_when_busy() -> None:
    """Registering a second run without overlap permissions should fail."""

    config = CronTriggerConfig(expression="0 * * * *", allow_overlapping=False)
    state = CronTriggerState(config)

    state.register_run(uuid4())

    with pytest.raises(CronOverlapError):
        state.register_run(uuid4())


def test_cron_trigger_consume_without_schedule() -> None:
    """Consuming without priming the schedule should raise an error."""

    state = CronTriggerState()

    with pytest.raises(CronValidationError):
        state.consume_due()


def test_cron_occurrence_respects_start_and_end_window() -> None:
    """Occurrences should snap to the configured window bounds."""

    start = datetime(2025, 1, 1, 9, 0, tzinfo=UTC)
    config = CronTriggerConfig(
        expression="0 9 * * *",
        timezone="UTC",
        start_at=start,
        end_at=start,
    )

    occurrence = config.to_occurrence()

    before_window = datetime(2025, 1, 1, 8, 0, tzinfo=UTC)
    next_due = occurrence.next_after(before_window, inclusive=False)
    assert next_due == start

    assert occurrence.next_after(start, inclusive=False) is None


def test_cron_trigger_rejects_invalid_expression() -> None:
    """Invalid cron expressions should raise a validation error."""

    with pytest.raises(ValidationError) as exc:
        CronTriggerConfig(expression="not-a-cron")

    assert "Invalid cron expression" in str(exc.value)


def test_cron_trigger_allows_missing_boundaries() -> None:
    """Explicitly passing None boundaries should be accepted."""

    config = CronTriggerConfig(start_at=None, end_at=None)

    assert config.start_at is None
    assert config.end_at is None


@pytest.mark.parametrize("boundary", ["start_at", "end_at"])
def test_cron_trigger_requires_timezone_aware_boundaries(boundary: str) -> None:
    """Boundary datetimes must include timezone information."""

    naive = datetime(2025, 1, 1, 9, 0)

    with pytest.raises(ValidationError) as exc:
        CronTriggerConfig(**{boundary: naive})

    assert "timezone-aware" in str(exc.value)


def test_cron_trigger_requires_minute_aligned_boundaries() -> None:
    """Boundary datetimes must align exactly to minute intervals."""

    misaligned = datetime(2025, 1, 1, 9, 0, 30, tzinfo=UTC)

    with pytest.raises(ValidationError) as exc:
        CronTriggerConfig(start_at=misaligned)

    assert "align to whole minutes" in str(exc.value)


def test_cron_trigger_start_must_precede_end() -> None:
    """start_at must be earlier than end_at when both are provided."""

    start = datetime(2025, 1, 2, 9, 0, tzinfo=UTC)
    end = datetime(2025, 1, 1, 9, 0, tzinfo=UTC)

    with pytest.raises(ValidationError) as exc:
        CronTriggerConfig(start_at=start, end_at=end)

    assert "start_at must be earlier" in str(exc.value)


def test_cron_trigger_rejects_invalid_timezone() -> None:
    """Invalid timezone identifiers should raise a validation error."""

    with pytest.raises(ValidationError):
        CronTriggerConfig(expression="0 * * * *", timezone="Mars/Phobos")


def test_cron_state_with_last_dispatched_at_computes_next_correctly() -> None:
    """When last_dispatched_at is provided, the next fire time is computed from it."""
    config = CronTriggerConfig(expression="0 9 * * *", timezone="UTC")

    # Simulate a scenario where a cron was dispatched yesterday at 9 AM
    last_dispatched = datetime(2025, 1, 1, 9, 0, tzinfo=UTC)
    state = CronTriggerState(config, last_dispatched_at=last_dispatched)

    # Even if we peek at a time later today (after 9 AM), it should NOT be due
    # because the last dispatch was today at 9 AM
    later_today = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    due = state.peek_due(now=later_today)
    assert due is None

    # It should be due tomorrow at 9 AM
    tomorrow_9am = datetime(2025, 1, 2, 9, 0, tzinfo=UTC)
    due_tomorrow = state.peek_due(now=tomorrow_9am)
    assert due_tomorrow == tomorrow_9am


def test_cron_state_without_last_dispatched_uses_now_as_reference() -> None:
    """When no last_dispatched_at is set, use 'now' as the reference."""
    config = CronTriggerConfig(expression="0 9 * * *", timezone="UTC")
    state = CronTriggerState(config)

    # At 12:00 PM, the next occurrence is tomorrow 9 AM (not today)
    now_12pm = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    due = state.peek_due(now=now_12pm)
    assert due is None  # Not due yet

    # Check that _next_fire_at is tomorrow 9 AM
    expected_next = datetime(2025, 1, 2, 9, 0, tzinfo=UTC)
    assert state._next_fire_at == expected_next


def test_cron_consume_updates_last_dispatched_at() -> None:
    """Consuming a due cron should update last_dispatched_at."""
    config = CronTriggerConfig(expression="0 9 * * *", timezone="UTC")
    state = CronTriggerState(config)

    # Prime the schedule at 9 AM
    now_9am = datetime(2025, 1, 1, 9, 0, tzinfo=UTC)
    due = state.peek_due(now=now_9am)
    assert due == now_9am

    # Before consume, last_dispatched_at is None
    assert state.last_dispatched_at is None

    # Consume the due time
    consumed = state.consume_due()
    assert consumed == now_9am

    # After consume, last_dispatched_at is updated
    assert state.last_dispatched_at == now_9am


def test_cron_state_with_start_at_and_last_dispatched_prefers_last_dispatched() -> None:
    """When both start_at and last_dispatched_at are set, use last_dispatched_at."""
    # start_at is in the past
    start_at = datetime(2024, 1, 1, 9, 0, tzinfo=UTC)
    config = CronTriggerConfig(
        expression="0 9 * * *", timezone="UTC", start_at=start_at
    )

    # last_dispatched_at is more recent
    last_dispatched = datetime(2025, 1, 1, 9, 0, tzinfo=UTC)
    state = CronTriggerState(config, last_dispatched_at=last_dispatched)

    # At 12:00 PM on Jan 1, 2025, should NOT be due (last dispatch was today)
    now_12pm = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    due = state.peek_due(now=now_12pm)
    assert due is None

    # Should be due tomorrow at 9 AM
    tomorrow_9am = datetime(2025, 1, 2, 9, 0, tzinfo=UTC)
    due_tomorrow = state.peek_due(now=tomorrow_9am)
    assert due_tomorrow == tomorrow_9am
