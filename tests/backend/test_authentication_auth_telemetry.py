"""AuthTelemetry unit tests."""

from __future__ import annotations
from orcheo_backend.app.authentication import (
    AuthEvent,
    AuthTelemetry,
    RequestContext,
    ServiceTokenRecord,
)


def test_auth_telemetry_record_event() -> None:
    """AuthTelemetry records events and updates counters."""

    telemetry = AuthTelemetry()
    event = AuthEvent(
        event="test",
        status="success",
        subject="user-1",
        identity_type="user",
        token_id="token-1",
    )

    telemetry.record(event)

    assert len(telemetry.events()) == 1
    assert telemetry.metrics()["test:success"] == 1


def test_auth_telemetry_record_auth_success() -> None:
    """record_auth_success creates a success event."""

    telemetry = AuthTelemetry()
    context = RequestContext(subject="svc-1", identity_type="service", token_id="svc")

    telemetry.record_auth_success(context, ip="1.2.3.4")

    events = telemetry.events()
    assert len(events) == 1
    assert events[0].event == "authenticate"
    assert events[0].status == "success"
    assert events[0].ip == "1.2.3.4"
    assert events[0].subject == "svc-1"
    assert events[0].token_id == "svc"


def test_auth_telemetry_record_auth_failure() -> None:
    """record_auth_failure creates a failure event."""

    telemetry = AuthTelemetry()

    telemetry.record_auth_failure(reason="invalid_token", ip="1.2.3.4")

    events = telemetry.events()
    assert len(events) == 1
    assert events[0].event == "authenticate"
    assert events[0].status == "failure"
    assert events[0].detail == "invalid_token"


def test_auth_telemetry_record_service_token_event() -> None:
    """record_service_token_event records lifecycle events."""

    telemetry = AuthTelemetry()
    record = ServiceTokenRecord(identifier="token-1", secret_hash="hash123")

    telemetry.record_service_token_event("mint", record)

    events = telemetry.events()
    assert len(events) == 1
    assert events[0].event == "service_token.mint"


def test_auth_telemetry_reset() -> None:
    """reset() clears events and counters."""

    telemetry = AuthTelemetry()
    event = AuthEvent(
        event="test",
        status="success",
        subject="user-1",
        identity_type="user",
        token_id="token-1",
    )
    telemetry.record(event)

    telemetry.reset()

    assert len(telemetry.events()) == 0
    assert len(telemetry.metrics()) == 0
