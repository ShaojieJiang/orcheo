"""Shared storage for worker-scoped external agent status and login sessions."""

from __future__ import annotations
import json
import os
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from threading import RLock
from typing import cast
import redis
from orcheo.external_agents.providers import DEFAULT_PROVIDERS
from orcheo_backend.app.schemas.system import (
    ExternalAgentLoginSession,
    ExternalAgentLoginSessionState,
    ExternalAgentProviderName,
    ExternalAgentProviderState,
    ExternalAgentProviderStatus,
)


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SESSION_TTL_SECONDS = 60 * 60 * 4


def _utcnow() -> datetime:
    return datetime.now(UTC)


def list_external_agent_providers() -> list[ExternalAgentProviderName]:
    """Return the supported external agent providers in stable order."""
    return [
        ExternalAgentProviderName.CLAUDE_CODE,
        ExternalAgentProviderName.CODEX,
    ]


def default_external_agent_status(
    provider_name: ExternalAgentProviderName,
) -> ExternalAgentProviderStatus:
    """Build the default status payload for a provider."""
    provider = DEFAULT_PROVIDERS[provider_name.value]
    return ExternalAgentProviderStatus(
        provider=provider_name,
        display_name=provider.display_name,
        state=ExternalAgentProviderState.UNKNOWN,
        installed=False,
        authenticated=False,
    )


def is_terminal_login_state(state: ExternalAgentLoginSessionState) -> bool:
    """Return whether a login session no longer needs polling."""
    return state in {
        ExternalAgentLoginSessionState.AUTHENTICATED,
        ExternalAgentLoginSessionState.FAILED,
        ExternalAgentLoginSessionState.TIMED_OUT,
    }


class ExternalAgentRuntimeStore:
    """Persist external agent status in Redis with in-process fallback."""

    def __init__(self, redis_url: str = REDIS_URL) -> None:
        """Initialize a Redis-backed store with an in-memory fallback."""
        self._lock = RLock()
        self._provider_statuses: dict[str, ExternalAgentProviderStatus] = {}
        self._provider_environments: dict[str, dict[str, str]] = {}
        self._sessions: dict[str, ExternalAgentLoginSession] = {}
        self._session_inputs: dict[str, str] = {}
        self._redis: redis.Redis | None = None
        try:
            self._redis = redis.from_url(redis_url, decode_responses=True)
        except redis.RedisError:
            self._redis = None

    def list_provider_statuses(self) -> list[ExternalAgentProviderStatus]:
        """Return the current status for all supported providers."""
        statuses = [
            self.get_provider_status(provider_name)
            for provider_name in list_external_agent_providers()
        ]
        return [status.model_copy(deep=True) for status in statuses]

    def get_provider_status(
        self,
        provider_name: ExternalAgentProviderName,
    ) -> ExternalAgentProviderStatus:
        """Return one provider status or the default unknown payload."""
        payload = self._read_provider_payload(provider_name)
        if payload is None:
            return default_external_agent_status(provider_name)
        return payload.model_copy(deep=True)

    def save_provider_status(self, status: ExternalAgentProviderStatus) -> None:
        """Persist the latest status for one provider."""
        self._write_provider_payload(status)

    def get_provider_environment(
        self,
        provider_name: ExternalAgentProviderName,
    ) -> dict[str, str]:
        """Return persisted provider environment variables."""
        return dict(self._read_provider_environment_payload(provider_name))

    def save_provider_environment(
        self,
        provider_name: ExternalAgentProviderName,
        environ: Mapping[str, str],
    ) -> None:
        """Persist provider environment variables."""
        self._write_provider_environment_payload(provider_name, environ)

    def get_login_session(self, session_id: str) -> ExternalAgentLoginSession | None:
        """Return one stored login session if present."""
        payload = self._read_session_payload(session_id)
        return payload.model_copy(deep=True) if payload is not None else None

    def save_login_session(self, session: ExternalAgentLoginSession) -> None:
        """Persist one worker-side login session snapshot."""
        self._write_session_payload(session)

    def clear_provider_session(
        self,
        provider_name: ExternalAgentProviderName,
    ) -> ExternalAgentProviderStatus:
        """Clear the active session reference for one provider."""
        current = self.get_provider_status(provider_name)
        updated = current.model_copy(update={"active_session_id": None})
        self.save_provider_status(updated)
        return updated

    def save_login_input(self, session_id: str, input_text: str) -> None:
        """Persist one queued operator input for a login session."""
        self._write_session_input(session_id, input_text)

    def get_login_input(self, session_id: str) -> str | None:
        """Return the current queued operator input for a login session."""
        return self._read_session_input(session_id)

    def clear_login_input(self, session_id: str) -> None:
        """Clear any queued operator input for a login session."""
        self._delete_session_input(session_id)

    def _provider_key(self, provider_name: ExternalAgentProviderName) -> str:
        return f"orcheo:external_agents:provider:{provider_name.value}"

    def _session_key(self, session_id: str) -> str:
        return f"orcheo:external_agents:session:{session_id}"

    def _provider_environment_key(
        self, provider_name: ExternalAgentProviderName
    ) -> str:
        return f"orcheo:external_agents:provider-env:{provider_name.value}"

    def _session_input_key(self, session_id: str) -> str:
        return f"orcheo:external_agents:session-input:{session_id}"

    def _read_provider_payload(
        self,
        provider_name: ExternalAgentProviderName,
    ) -> ExternalAgentProviderStatus | None:
        if self._redis is not None:
            try:
                payload = self._redis.get(self._provider_key(provider_name))
                if payload:
                    return ExternalAgentProviderStatus.model_validate_json(
                        cast(str, payload)
                    )
            except redis.RedisError:
                pass
        with self._lock:
            payload = self._provider_statuses.get(provider_name.value)
            return payload.model_copy(deep=True) if payload is not None else None

    def _write_provider_payload(self, status: ExternalAgentProviderStatus) -> None:
        if self._redis is not None:
            try:
                self._redis.set(
                    self._provider_key(status.provider), status.model_dump_json()
                )
            except redis.RedisError:
                pass
        with self._lock:
            self._provider_statuses[status.provider.value] = status.model_copy(
                deep=True
            )

    def _read_provider_environment_payload(
        self,
        provider_name: ExternalAgentProviderName,
    ) -> dict[str, str]:
        if self._redis is not None:
            try:
                payload = self._redis.get(self._provider_environment_key(provider_name))
                if payload:  # pragma: no branch
                    decoded = json.loads(cast(str, payload))
                    if isinstance(decoded, dict):
                        return {
                            str(key): str(value)
                            for key, value in decoded.items()
                            if str(value).strip()
                        }
            except (redis.RedisError, json.JSONDecodeError):
                pass
        with self._lock:
            payload = self._provider_environments.get(provider_name.value, {})
            return dict(payload)

    def _write_provider_environment_payload(
        self,
        provider_name: ExternalAgentProviderName,
        environ: Mapping[str, str],
    ) -> None:
        payload = {key: value for key, value in environ.items() if value.strip()}
        if self._redis is not None:
            try:
                self._redis.set(
                    self._provider_environment_key(provider_name),
                    json.dumps(payload, sort_keys=True),
                )
            except redis.RedisError:
                pass
        with self._lock:
            self._provider_environments[provider_name.value] = dict(payload)

    def _read_session_payload(
        self, session_id: str
    ) -> ExternalAgentLoginSession | None:
        if self._redis is not None:
            try:
                payload = self._redis.get(self._session_key(session_id))
                if payload:
                    return ExternalAgentLoginSession.model_validate_json(
                        cast(str, payload)
                    )
            except redis.RedisError:
                pass
        with self._lock:
            payload = self._sessions.get(session_id)
            return payload.model_copy(deep=True) if payload is not None else None

    def _write_session_payload(self, session: ExternalAgentLoginSession) -> None:
        if self._redis is not None:
            try:
                self._redis.set(
                    self._session_key(session.session_id),
                    session.model_dump_json(),
                    ex=SESSION_TTL_SECONDS,
                )
            except redis.RedisError:
                pass
        with self._lock:
            self._sessions[session.session_id] = session.model_copy(deep=True)

    def _write_session_input(self, session_id: str, input_text: str) -> None:
        if self._redis is not None:
            try:
                self._redis.set(
                    self._session_input_key(session_id),
                    input_text,
                    ex=SESSION_TTL_SECONDS,
                )
            except redis.RedisError:
                pass
        with self._lock:
            self._session_inputs[session_id] = input_text

    def _read_session_input(self, session_id: str) -> str | None:
        if self._redis is not None:
            try:
                payload = self._redis.get(self._session_input_key(session_id))
                if payload is not None:
                    return cast(str, payload)
            except redis.RedisError:
                pass
        with self._lock:
            return self._session_inputs.get(session_id)

    def _delete_session_input(self, session_id: str) -> None:
        if self._redis is not None:
            try:
                self._redis.delete(self._session_input_key(session_id))
            except redis.RedisError:
                pass
        with self._lock:
            self._session_inputs.pop(session_id, None)


def list_active_login_sessions(
    sessions: Iterable[ExternalAgentLoginSession],
) -> list[ExternalAgentLoginSession]:
    """Return the login sessions that still need polling."""
    return [
        session for session in sessions if not is_terminal_login_state(session.state)
    ]


__all__ = [
    "ExternalAgentRuntimeStore",
    "default_external_agent_status",
    "is_terminal_login_state",
    "list_active_login_sessions",
    "list_external_agent_providers",
]
