"""In-memory browser context store with TTL eviction and focus-priority."""

from __future__ import annotations
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(slots=True)
class BrowserContextEntry:
    """A single browser tab's context."""

    session_id: str
    page: str
    workflow_id: str | None
    workflow_name: str | None
    focused: bool
    last_seen: datetime
    last_focused_at: datetime | None = None


class BrowserContextStore:
    """In-memory context store keyed by session_id with TTL eviction.

    Thread-safe. Entries are evicted after ``ttl_seconds`` without an update.
    Focus-priority resolution returns the session with the most recent
    ``last_focused_at``, falling back to the most recently seen session.
    """

    def __init__(self, ttl_seconds: int = 300) -> None:
        """Create a store with the given TTL in seconds."""
        self._ttl = timedelta(seconds=ttl_seconds)
        self._sessions: dict[str, BrowserContextEntry] = {}
        self._lock = threading.Lock()
        self._cleanup_timer: threading.Timer | None = None
        self._start_periodic_cleanup()

    def upsert(
        self,
        *,
        session_id: str,
        page: str,
        workflow_id: str | None,
        workflow_name: str | None,
        focused: bool,
        timestamp: datetime | None = None,
    ) -> None:
        """Insert or update a session entry. Resets the TTL."""
        now = timestamp or datetime.now(UTC)
        with self._lock:
            existing = self._sessions.get(session_id)
            last_focused_at = existing.last_focused_at if existing else None
            if focused:
                last_focused_at = now
            self._sessions[session_id] = BrowserContextEntry(
                session_id=session_id,
                page=page,
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                focused=focused,
                last_seen=now,
                last_focused_at=last_focused_at,
            )

    def _start_periodic_cleanup(self) -> None:
        """Schedule a background cleanup every TTL interval."""
        interval = self._ttl.total_seconds()
        self._cleanup_timer = threading.Timer(interval, self._periodic_cleanup)
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()

    def _periodic_cleanup(self) -> None:
        """Run eviction and reschedule the next cleanup."""
        now = datetime.now(UTC)
        with self._lock:
            self._evict(now)
        self._start_periodic_cleanup()

    def _evict(self, now: datetime) -> None:
        """Remove entries older than TTL. Must be called under lock."""
        cutoff = now - self._ttl
        expired = [
            sid for sid, entry in self._sessions.items() if entry.last_seen < cutoff
        ]
        for sid in expired:
            del self._sessions[sid]

    def get_active(self) -> dict[str, object]:
        """Return the active context using focus-priority resolution.

        Returns the session with the most recent ``last_focused_at``.
        If no session has focus history, returns the most recently seen.
        If no sessions exist, returns a null context.
        """
        now = datetime.now(UTC)
        with self._lock:
            self._evict(now)
            if not self._sessions:
                return {
                    "session_id": None,
                    "page": None,
                    "workflow_id": None,
                    "workflow_name": None,
                    "focused": False,
                    "last_focused_at": None,
                    "staleness_seconds": 0,
                    "total_sessions": 0,
                }

            total = len(self._sessions)

            # Focus-priority: pick session with most recent last_focused_at
            focused_entries = [
                e for e in self._sessions.values() if e.last_focused_at is not None
            ]
            if focused_entries:
                best = max(
                    focused_entries,
                    key=lambda e: e.last_focused_at or datetime.min.replace(tzinfo=UTC),
                )
            else:
                best = max(self._sessions.values(), key=lambda e: e.last_seen)

            staleness = (now - best.last_seen).total_seconds()
            return {
                "session_id": best.session_id,
                "page": best.page,
                "workflow_id": best.workflow_id,
                "workflow_name": best.workflow_name,
                "focused": best.focused,
                "last_focused_at": (
                    best.last_focused_at.isoformat() if best.last_focused_at else None
                ),
                "staleness_seconds": int(staleness),
                "total_sessions": total,
            }

    def get_all_sessions(self) -> list[dict[str, object]]:
        """Return all active (non-expired) sessions."""
        now = datetime.now(UTC)
        with self._lock:
            self._evict(now)
            results: list[dict[str, object]] = []
            for entry in sorted(
                self._sessions.values(), key=lambda e: e.last_seen, reverse=True
            ):
                staleness = (now - entry.last_seen).total_seconds()
                results.append(
                    {
                        "session_id": entry.session_id,
                        "page": entry.page,
                        "workflow_id": entry.workflow_id,
                        "workflow_name": entry.workflow_name,
                        "focused": entry.focused,
                        "last_seen": entry.last_seen.isoformat(),
                        "last_focused_at": (
                            entry.last_focused_at.isoformat()
                            if entry.last_focused_at
                            else None
                        ),
                        "staleness_seconds": int(staleness),
                    }
                )
            return results
