from __future__ import annotations
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal
from .context import RequestContext


if TYPE_CHECKING:
    from .service_tokens import ServiceTokenRecord


@dataclass(slots=True)
class AuthEvent:
    """Structured record describing an authentication-related event."""

    event: str
    status: Literal["success", "failure"]
    subject: str | None
    identity_type: str | None
    token_id: str | None
    ip: str | None = None
    detail: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


class AuthTelemetry:
    """Collect authentication audit events and counters in-memory."""

    def __init__(self, *, max_events: int = 512) -> None:
        """Initialise the telemetry sink with bounded storage."""
        self._events: deque[AuthEvent] = deque(maxlen=max_events)
        self._counters: Counter[str] = Counter()

    def record(self, event: AuthEvent) -> None:
        """Append an event to the audit log and increment counters."""
        self._events.append(event)
        counter_key = f"{event.event}:{event.status}"
        self._counters[counter_key] += 1

    def record_auth_success(
        self, context: RequestContext, *, ip: str | None = None
    ) -> None:
        """Record a successful authentication event."""
        self.record(
            AuthEvent(
                event="authenticate",
                status="success",
                subject=context.subject,
                identity_type=context.identity_type,
                token_id=context.token_id,
                ip=ip,
            )
        )

    def record_auth_failure(self, *, reason: str, ip: str | None = None) -> None:
        """Record a failed authentication attempt."""
        self.record(
            AuthEvent(
                event="authenticate",
                status="failure",
                subject=None,
                identity_type=None,
                token_id=None,
                ip=ip,
                detail=reason,
            )
        )

    def record_service_token_event(
        self, action: str, record: ServiceTokenRecord
    ) -> None:
        """Record lifecycle activity for a managed service token."""
        self.record(
            AuthEvent(
                event=f"service_token.{action}",
                status="success",
                subject=record.identifier,
                identity_type="service",
                token_id=record.identifier,
            )
        )

    def metrics(self) -> dict[str, int]:
        """Return a snapshot of aggregated counters."""
        return dict(self._counters)

    def events(self) -> tuple[AuthEvent, ...]:
        """Return recent authentication events in chronological order."""
        return tuple(self._events)

    def reset(self) -> None:
        """Clear stored events and counters."""
        self._events.clear()
        self._counters.clear()


auth_telemetry = AuthTelemetry()
