from datetime import UTC, datetime
import pytest
from pydantic import ValidationError
from orcheo.triggers.http_polling import (
    HttpPollingDispatchPlan,
    HttpPollingTriggerConfig,
    HttpPollingTriggerState,
    HttpPollingValidationError,
)


def test_http_polling_config_normalizes_mappings() -> None:
    """HTTP polling config normalizes method, headers, and query params."""

    config = HttpPollingTriggerConfig(
        url="https://api.example.com/data",
        method="post",
        headers={"Authorization": "Bearer token"},
        query_params={"limit": "10"},
        deduplicate_on="/id",
    )

    assert config.method == "POST"
    assert config.headers == {"Authorization": "Bearer token"}
    assert config.query_params == {"limit": "10"}
    assert config.deduplicate_on == "/id"


def test_http_polling_config_rejects_invalid_pointer() -> None:
    """Invalid JSON pointers raise a domain-specific error."""

    with pytest.raises(ValidationError) as exc:
        HttpPollingTriggerConfig(
            url="https://api.example.com/data",
            deduplicate_on="id",
        )
    error = exc.value.errors()[0]["ctx"]["error"]
    assert isinstance(error, HttpPollingValidationError)


def test_http_polling_state_generates_dispatch_plan() -> None:
    """Trigger state computes the next poll and advances schedule."""

    config = HttpPollingTriggerConfig(
        url="https://api.example.com/data",
        interval_seconds=60,
    )
    state = HttpPollingTriggerState(config)

    now = datetime(2024, 1, 1, tzinfo=UTC)
    next_poll = state.ensure_next_poll(now=now)
    assert next_poll > now

    plan = state.consume_poll(now=now)
    assert isinstance(plan, HttpPollingDispatchPlan)
    assert plan.request_url == "https://api.example.com/data"
    assert plan.method == "GET"

    future_poll = state.ensure_next_poll(now=now)
    assert future_poll > plan.scheduled_for

    subsequent_plan = state.consume_poll()
    assert subsequent_plan.scheduled_for > plan.scheduled_for

    config_copy = state.config
    assert config_copy.interval_seconds == 60

    state.update_config(
        HttpPollingTriggerConfig(
            url="https://api.example.com/data", interval_seconds=120
        )
    )
    naive_now = datetime(2024, 1, 1, 0, 1, 0)
    updated_poll = state.ensure_next_poll(now=naive_now)
    assert updated_poll.tzinfo == UTC
