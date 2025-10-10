from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from orcheo.triggers.cron import CronTriggerConfig, CronTriggerState


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


def test_cron_trigger_rejects_invalid_timezone() -> None:
    """Invalid timezone identifiers should raise a validation error."""

    with pytest.raises(ValidationError):
        CronTriggerConfig(expression="0 * * * *", timezone="Mars/Phobos")
