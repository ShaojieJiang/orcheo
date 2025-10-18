"""Additional coverage for backend application helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, Request, status
from starlette.types import Message

from orcheo.models import CredentialHealthStatus
from orcheo.vault import FileCredentialVault, InMemoryCredentialVault
from orcheo.vault.oauth import (
    CredentialHealthError,
    CredentialHealthReport,
    CredentialHealthResult,
)
from orcheo.triggers.manual import ManualDispatchItem, ManualDispatchRequest
from orcheo_backend.app import (
    _credential_service_ref,
    _create_vault,
    _ensure_credential_service,
    _settings_value,
    _vault_ref,
    create_app,
    dispatch_cron_triggers,
    dispatch_manual_runs,
    get_credential_service,
    get_workflow_credential_health,
    invoke_webhook_trigger,
    validate_workflow_credentials,
)
from orcheo_backend.app.repository import WorkflowNotFoundError
from orcheo_backend.app.schemas import CredentialValidationRequest


def test_settings_value_returns_default_when_attribute_missing() -> None:
    """Accessing a missing attribute path falls back to the provided default."""

    settings = SimpleNamespace(vault=SimpleNamespace())

    value = _settings_value(
        settings,
        attr_path="vault.backend",
        env_key="VAULT_BACKEND",
        default="inmemory",
    )

    assert value == "inmemory"


def test_settings_value_reads_nested_attribute() -> None:
    """Nested attribute paths return the stored value when present."""

    settings = SimpleNamespace(vault=SimpleNamespace(token=SimpleNamespace(ttl=60)))

    value = _settings_value(
        settings,
        attr_path="vault.token.ttl",
        env_key="VAULT_TOKEN_TTL",
        default=30,
    )

    assert value == 60


def test_settings_value_prefers_mapping_get() -> None:
    """Mapping-like settings use the ``get`` method when available."""

    settings = {"VAULT_BACKEND": "sqlite"}
    value = _settings_value(
        settings,
        attr_path="vault.backend",
        env_key="VAULT_BACKEND",
        default="inmemory",
    )

    assert value == "sqlite"


def test_settings_value_without_attr_path_returns_default() -> None:
    value = _settings_value({}, attr_path=None, env_key="MISSING", default=42)
    assert value == 42


def test_settings_value_handles_missing_root_attribute() -> None:
    settings = SimpleNamespace()
    value = _settings_value(
        settings,
        attr_path="vault.backend",
        env_key="VAULT_BACKEND",
        default="fallback",
    )
    assert value == "fallback"


def test_create_vault_supports_file_backend(tmp_path: Path) -> None:
    """File-backed vaults expand the configured path and return an instance."""

    path = tmp_path / "orcheo" / "vault.sqlite"
    settings = SimpleNamespace(
        vault=SimpleNamespace(
            backend="file",
            local_path=str(path),
            encryption_key="unit-test-key",
        )
    )

    vault = _create_vault(settings)  # type: ignore[arg-type]

    assert isinstance(vault, FileCredentialVault)
    assert vault._path == path.expanduser()  # type: ignore[attr-defined]


def test_create_vault_rejects_unsupported_backend() -> None:
    """Unsupported vault backends raise a clear error message."""

    settings = SimpleNamespace(vault=SimpleNamespace(backend="aws_kms"))

    with pytest.raises(ValueError, match="not supported"):
        _create_vault(settings)  # type: ignore[arg-type]


def test_ensure_credential_service_initializes_and_caches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Credential services are created once and cached for subsequent calls."""

    settings = SimpleNamespace(vault=SimpleNamespace(backend="inmemory"))

    monkeypatch.setitem(_vault_ref, "vault", None)
    monkeypatch.setitem(_credential_service_ref, "service", None)

    first = _ensure_credential_service(settings)  # type: ignore[arg-type]
    second = _ensure_credential_service(settings)  # type: ignore[arg-type]

    assert first is second
    assert _vault_ref["vault"] is not None


def test_ensure_credential_service_returns_existing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()
    monkeypatch.setitem(_credential_service_ref, "service", sentinel)

    service = _ensure_credential_service(SimpleNamespace())  # type: ignore[arg-type]

    assert service is sentinel


def test_ensure_credential_service_reuses_existing_vault(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault = InMemoryCredentialVault()
    monkeypatch.setitem(_vault_ref, "vault", vault)
    monkeypatch.setitem(_credential_service_ref, "service", None)

    service = _ensure_credential_service(SimpleNamespace())  # type: ignore[arg-type]

    assert service is not None
    assert _vault_ref["vault"] is vault


class _MissingWorkflowRepository:
    async def get_workflow(self, workflow_id):  # pragma: no cover - signature typing
        raise WorkflowNotFoundError("missing")


@pytest.mark.asyncio()
async def test_get_workflow_credential_health_handles_missing_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The credential health endpoint raises a 404 for unknown workflows."""

    monkeypatch.setitem(_credential_service_ref, "service", None)

    with pytest.raises(HTTPException) as exc_info:
        await get_workflow_credential_health(
            uuid4(),
            repository=_MissingWorkflowRepository(),
            service=None,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_get_workflow_credential_health_returns_unknown_response() -> None:
    """A missing cached report results in an UNKNOWN response payload."""

    class Repository:
        async def get_workflow(self, workflow_id):  # noqa: D401 - simple stub
            return object()

    class Service:
        def get_report(self, workflow_id):
            return None

    response = await get_workflow_credential_health(
        uuid4(), repository=Repository(), service=Service()
    )

    assert response.status is CredentialHealthStatus.UNKNOWN
    assert response.credentials == []


@pytest.mark.asyncio()
async def test_get_workflow_credential_health_requires_service() -> None:
    class Repository:
        async def get_workflow(self, workflow_id):
            return object()

    with pytest.raises(HTTPException) as exc_info:
        await get_workflow_credential_health(
            uuid4(), repository=Repository(), service=None
        )

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.asyncio()
async def test_validate_workflow_credentials_reports_failures() -> None:
    workflow_id = uuid4()

    class Repository:
        async def get_workflow(self, workflow_id):
            return object()

    class Service:
        async def ensure_workflow_health(self, workflow_id, *, actor=None):
            report = CredentialHealthReport(
                workflow_id=workflow_id,
                results=[
                    CredentialHealthResult(
                        credential_id=uuid4(),
                        name="Slack",
                        provider="slack",
                        status=CredentialHealthStatus.UNHEALTHY,
                        last_checked_at=datetime.now(tz=UTC),
                        failure_reason="expired",
                    )
                ],
                checked_at=datetime.now(tz=UTC),
            )
            return report

    request = CredentialValidationRequest(actor="ops")
    with pytest.raises(HTTPException) as exc_info:
        await validate_workflow_credentials(
            workflow_id,
            request,
            repository=Repository(),
            service=Service(),
        )

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio()
async def test_validate_workflow_credentials_handles_missing_workflow() -> None:
    request = CredentialValidationRequest(actor="ops")

    with pytest.raises(HTTPException) as exc_info:
        await validate_workflow_credentials(
            uuid4(),
            request,
            repository=_MissingWorkflowRepository(),
            service=None,
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


def _health_error(workflow_id: UUID) -> CredentialHealthError:
    report = CredentialHealthReport(
        workflow_id=workflow_id,
        results=[
            CredentialHealthResult(
                credential_id=uuid4(),
                name="Slack",
                provider="slack",
                status=CredentialHealthStatus.UNHEALTHY,
                last_checked_at=datetime.now(tz=UTC),
                failure_reason="expired",
            )
        ],
        checked_at=datetime.now(tz=UTC),
    )
    return CredentialHealthError(report)


@pytest.mark.asyncio()
async def test_validate_workflow_credentials_requires_service() -> None:
    workflow_id = uuid4()

    class Repository:
        async def get_workflow(self, workflow_id):
            return object()

    request = CredentialValidationRequest(actor="ops")
    with pytest.raises(HTTPException) as exc_info:
        await validate_workflow_credentials(
            workflow_id,
            request,
            repository=Repository(),
            service=None,
        )

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.asyncio()
async def test_invoke_webhook_trigger_wraps_health_error() -> None:
    workflow_id = uuid4()

    class Repository:
        async def handle_webhook_trigger(self, *args, **kwargs):
            raise _health_error(workflow_id)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
    }

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(scope, receive)

    with pytest.raises(HTTPException) as exc_info:
        await invoke_webhook_trigger(workflow_id, request, repository=Repository())

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio()
async def test_dispatch_cron_triggers_wraps_health_error() -> None:
    workflow_id = uuid4()

    class Repository:
        async def dispatch_due_cron_runs(self, now=None):
            raise _health_error(workflow_id)

    with pytest.raises(HTTPException) as exc_info:
        await dispatch_cron_triggers(repository=Repository())

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio()
async def test_dispatch_manual_runs_wraps_health_error() -> None:
    workflow_id = uuid4()

    class Repository:
        async def dispatch_manual_runs(self, request):
            raise _health_error(workflow_id)

    manual_request = ManualDispatchRequest(
        workflow_id=workflow_id,
        actor="ops",
        runs=[ManualDispatchItem(input_payload={})],
    )

    with pytest.raises(HTTPException) as exc_info:
        await dispatch_manual_runs(manual_request, repository=Repository())

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_create_app_infers_credential_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class CredentialService:
        pass

    class Repository:
        _credential_service = CredentialService()

    monkeypatch.setitem(_credential_service_ref, "service", None)
    app = create_app(Repository())
    resolver = app.dependency_overrides[get_credential_service]
    assert resolver() is Repository._credential_service
