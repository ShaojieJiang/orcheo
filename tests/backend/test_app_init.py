"""Additional coverage for backend application helpers."""

from __future__ import annotations
import os
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException, Request, status
from starlette.types import Message
from orcheo.models import (
    CredentialHealthStatus,
    CredentialKind,
    CredentialMetadata,
    CredentialScope,
)
from orcheo.models.workflow import Workflow, WorkflowRun, WorkflowVersion
from orcheo.triggers.manual import ManualDispatchItem, ManualDispatchRequest
from orcheo.triggers.webhook import WebhookValidationError
from orcheo.vault import (
    FileCredentialVault,
    InMemoryCredentialVault,
    WorkflowScopeError,
)
from orcheo.vault.oauth import (
    CredentialHealthError,
    CredentialHealthReport,
    CredentialHealthResult,
)
from orcheo_backend.app import (
    _create_vault,
    _credential_service_ref,
    _ensure_credential_service,
    _ensure_file_vault_key,
    _raise_conflict,
    _raise_not_found,
    _raise_scope_error,
    _raise_webhook_error,
    _settings_value,
    _vault_ref,
    archive_workflow,
    create_app,
    create_chatkit_session_endpoint,
    create_workflow,
    dispatch_cron_triggers,
    dispatch_manual_runs,
    get_credential_service,
    get_workflow,
    get_workflow_credential_health,
    invoke_webhook_trigger,
    list_workflow_execution_histories,
    list_workflows,
    trigger_chatkit_workflow,
    update_workflow,
    validate_workflow_credentials,
)
from orcheo_backend.app.history import RunHistoryRecord
from orcheo_backend.app.repository import (
    WorkflowNotFoundError,
)
from orcheo_backend.app.schemas import (
    ChatKitSessionRequest,
    ChatKitWorkflowTriggerRequest,
    CredentialValidationRequest,
    WorkflowCreateRequest,
    WorkflowUpdateRequest,
)


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


def test_create_vault_generates_encryption_key(tmp_path: Path) -> None:
    """Missing encryption keys are generated and stored alongside the database."""

    path = tmp_path / "vault.sqlite"
    settings = SimpleNamespace(
        vault=SimpleNamespace(
            backend="file",
            local_path=str(path),
            encryption_key=None,
        )
    )

    vault = _create_vault(settings)  # type: ignore[arg-type]

    assert isinstance(vault, FileCredentialVault)
    key_path = path.with_name(f"{path.stem}.key")
    assert key_path.exists()
    key_contents = key_path.read_text(encoding="utf-8").strip()
    assert len(key_contents) == 64

    _create_vault(settings)  # type: ignore[arg-type]

    assert key_path.read_text(encoding="utf-8").strip() == key_contents


def test_ensure_file_vault_key_returns_existing_value(tmp_path: Path) -> None:
    path = tmp_path / "vault.sqlite"
    key_path = path.with_name(f"{path.stem}.key")
    key_path.write_text(" existing-key ", encoding="utf-8")

    key = _ensure_file_vault_key(path, None)

    assert key == "existing-key"
    assert key_path.read_text(encoding="utf-8") == " existing-key "


def test_ensure_file_vault_key_regenerates_when_existing_blank(tmp_path: Path) -> None:
    path = tmp_path / "vault.sqlite"
    key_path = path.with_name(f"{path.stem}.key")
    key_path.write_text("   \n", encoding="utf-8")

    key = _ensure_file_vault_key(path, None)

    assert len(key) == 64
    assert key_path.read_text(encoding="utf-8").strip() == key


def test_ensure_file_vault_key_handles_chmod_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "vault.sqlite"
    calls: list[tuple[Path, int]] = []

    def raise_permission_error(target: Path, mode: int) -> None:
        calls.append((target, mode))
        raise PermissionError("chmod not permitted")

    monkeypatch.setattr(os, "chmod", raise_permission_error)

    key = _ensure_file_vault_key(path, None)

    key_path = path.with_name(f"{path.stem}.key")
    assert key_path.exists()
    assert len(key) == 64
    assert calls and calls[0][0] == key_path


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


@pytest.mark.asyncio()
async def test_list_workflow_execution_histories_returns_records() -> None:
    """The execution history endpoint returns a list of history responses."""
    workflow_id = uuid4()
    execution_id_1 = str(uuid4())
    execution_id_2 = str(uuid4())

    class HistoryStore:
        async def list_histories(self, workflow_id: str, limit: int):
            return [
                RunHistoryRecord(
                    workflow_id=workflow_id,
                    execution_id=execution_id_1,
                    inputs={"param": "value1"},
                ),
                RunHistoryRecord(
                    workflow_id=workflow_id,
                    execution_id=execution_id_2,
                    inputs={"param": "value2"},
                ),
            ]

    response = await list_workflow_execution_histories(
        workflow_id=workflow_id,
        history_store=HistoryStore(),
        limit=50,
    )

    assert len(response) == 2
    assert response[0].execution_id == execution_id_1
    assert response[1].execution_id == execution_id_2
    assert response[0].inputs == {"param": "value1"}
    assert response[1].inputs == {"param": "value2"}


@pytest.mark.asyncio()
async def test_list_workflow_execution_histories_respects_limit() -> None:
    """The execution history endpoint passes limit to the store."""
    workflow_id = uuid4()
    limit_value = None

    class HistoryStore:
        async def list_histories(self, workflow_id: str, limit: int):
            nonlocal limit_value
            limit_value = limit
            return []

    await list_workflow_execution_histories(
        workflow_id=workflow_id,
        history_store=HistoryStore(),
        limit=100,
    )

    assert limit_value == 100


# Test helper functions for error raising


def test_raise_not_found_raises_404() -> None:
    """The _raise_not_found helper raises a 404 HTTPException."""
    with pytest.raises(HTTPException) as exc_info:
        _raise_not_found("Test not found", ValueError("test"))
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Test not found"


def test_raise_conflict_raises_409() -> None:
    """The _raise_conflict helper raises a 409 HTTPException."""
    with pytest.raises(HTTPException) as exc_info:
        _raise_conflict("Test conflict", ValueError("test"))
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Test conflict"


def test_raise_webhook_error_raises_with_status_code() -> None:
    """_raise_webhook_error raises HTTPException with webhook error status."""
    webhook_error = WebhookValidationError("Invalid signature", status_code=401)
    with pytest.raises(HTTPException) as exc_info:
        _raise_webhook_error(webhook_error)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid signature"


def test_raise_scope_error_raises_403() -> None:
    """The _raise_scope_error helper raises a 403 HTTPException."""
    scope_error = WorkflowScopeError("Access denied")
    with pytest.raises(HTTPException) as exc_info:
        _raise_scope_error(scope_error)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Access denied"


# Test ChatKit endpoints


@pytest.mark.asyncio()
async def test_create_chatkit_session_endpoint_returns_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ChatKit session endpoint returns client secret from environment."""
    monkeypatch.setenv("CHATKIT_CLIENT_SECRET", "test-secret-123")

    request = ChatKitSessionRequest(workflow_id=None)
    response = await create_chatkit_session_endpoint(request)

    assert response.client_secret == "test-secret-123"


@pytest.mark.asyncio()
async def test_create_chatkit_session_endpoint_workflow_specific(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ChatKit session endpoint prefers workflow-specific secret."""
    workflow_id = uuid4()
    workflow_key = str(workflow_id).replace("-", "").upper()
    monkeypatch.setenv(f"CHATKIT_CLIENT_SECRET_{workflow_key}", "workflow-secret")
    monkeypatch.setenv("CHATKIT_CLIENT_SECRET", "generic-secret")

    request = ChatKitSessionRequest(workflow_id=workflow_id)
    response = await create_chatkit_session_endpoint(request)

    assert response.client_secret == "workflow-secret"


@pytest.mark.asyncio()
async def test_create_chatkit_session_endpoint_missing_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ChatKit session endpoint raises 503 when secret is not configured."""
    monkeypatch.delenv("CHATKIT_CLIENT_SECRET", raising=False)

    request = ChatKitSessionRequest(workflow_id=None)
    with pytest.raises(HTTPException) as exc_info:
        await create_chatkit_session_endpoint(request)

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio()
async def test_trigger_chatkit_workflow_creates_run() -> None:
    """ChatKit trigger creates a workflow run."""
    workflow_id = uuid4()
    run_id = uuid4()

    class Repository:
        async def get_latest_version(self, wf_id):
            return WorkflowVersion(
                id=uuid4(),
                workflow_id=wf_id,
                version=1,
                graph={},
                created_by="system",
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

        async def create_run(
            self, wf_id, workflow_version_id, triggered_by, input_payload
        ):
            return WorkflowRun(
                id=run_id,
                workflow_version_id=workflow_version_id,
                triggered_by=triggered_by,
                input_payload=input_payload,
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    request = ChatKitWorkflowTriggerRequest(
        message="Hello",
        client_thread_id="thread-123",
        actor="user@example.com",
    )

    result = await trigger_chatkit_workflow(workflow_id, request, Repository())

    assert result.id == run_id
    assert result.triggered_by == "user@example.com"


@pytest.mark.asyncio()
async def test_trigger_chatkit_workflow_missing_workflow() -> None:
    """ChatKit trigger raises 404 for missing workflow."""
    workflow_id = uuid4()

    class Repository:
        async def get_latest_version(self, wf_id):
            raise WorkflowNotFoundError("not found")

    request = ChatKitWorkflowTriggerRequest(
        message="Hello",
        client_thread_id="thread-123",
        actor="user@example.com",
    )

    with pytest.raises(HTTPException) as exc_info:
        await trigger_chatkit_workflow(workflow_id, request, Repository())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_trigger_chatkit_workflow_credential_health_error() -> None:
    """ChatKit trigger handles credential health errors."""
    workflow_id = uuid4()

    class Repository:
        async def get_latest_version(self, wf_id):
            return WorkflowVersion(
                id=uuid4(),
                workflow_id=wf_id,
                version=1,
                graph={},
                created_by="system",
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

        async def create_run(
            self, wf_id, workflow_version_id, triggered_by, input_payload
        ):
            raise _health_error(wf_id)

    request = ChatKitWorkflowTriggerRequest(
        message="Hello",
        client_thread_id="thread-123",
        actor="user@example.com",
    )

    with pytest.raises(HTTPException) as exc_info:
        await trigger_chatkit_workflow(workflow_id, request, Repository())

    assert exc_info.value.status_code == 422


# Test workflow CRUD endpoints


@pytest.mark.asyncio()
async def test_list_workflows_returns_all() -> None:
    """List workflows endpoint returns all workflows."""
    workflow1 = Workflow(
        id=uuid4(),
        name="Workflow 1",
        slug="workflow-1",
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )
    workflow2 = Workflow(
        id=uuid4(),
        name="Workflow 2",
        slug="workflow-2",
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )

    class Repository:
        async def list_workflows(self, *, include_archived: bool = False):
            return [workflow1, workflow2]

    result = await list_workflows(Repository(), include_archived=False)

    assert len(result) == 2
    assert result[0].id == workflow1.id
    assert result[1].id == workflow2.id


@pytest.mark.asyncio()
async def test_create_workflow_returns_new_workflow() -> None:
    """Create workflow endpoint creates and returns new workflow."""
    workflow_id = uuid4()

    class Repository:
        async def create_workflow(self, name, slug, description, tags, actor):
            return Workflow(
                id=workflow_id,
                name=name,
                slug=slug,
                description=description,
                tags=tags,
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    request = WorkflowCreateRequest(
        name="Test Workflow",
        slug="test-workflow",
        description="A test workflow",
        tags=["test"],
        actor="admin",
    )

    result = await create_workflow(request, Repository())

    assert result.id == workflow_id
    assert result.name == "Test Workflow"
    assert result.slug == "test-workflow"


@pytest.mark.asyncio()
async def test_get_workflow_returns_workflow() -> None:
    """Get workflow endpoint returns the requested workflow."""
    workflow_id = uuid4()

    class Repository:
        async def get_workflow(self, wf_id):
            return Workflow(
                id=wf_id,
                name="Test Workflow",
                slug="test-workflow",
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    result = await get_workflow(workflow_id, Repository())

    assert result.id == workflow_id
    assert result.name == "Test Workflow"


@pytest.mark.asyncio()
async def test_get_workflow_not_found() -> None:
    """Get workflow endpoint raises 404 for missing workflow."""
    workflow_id = uuid4()

    class Repository:
        async def get_workflow(self, wf_id):
            raise WorkflowNotFoundError("not found")

    with pytest.raises(HTTPException) as exc_info:
        await get_workflow(workflow_id, Repository())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_update_workflow_returns_updated() -> None:
    """Update workflow endpoint returns the updated workflow."""
    workflow_id = uuid4()

    class Repository:
        async def update_workflow(
            self, wf_id, name, description, tags, is_archived, actor
        ):
            return Workflow(
                id=wf_id,
                name=name or "Test Workflow",
                slug="test-workflow",
                description=description,
                tags=tags or [],
                is_archived=is_archived,
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    request = WorkflowUpdateRequest(
        name="Updated Workflow",
        description="Updated description",
        tags=["updated"],
        is_archived=False,
        actor="admin",
    )

    result = await update_workflow(workflow_id, request, Repository())

    assert result.id == workflow_id
    assert result.name == "Updated Workflow"


@pytest.mark.asyncio()
async def test_update_workflow_not_found() -> None:
    """Update workflow endpoint raises 404 for missing workflow."""
    workflow_id = uuid4()

    class Repository:
        async def update_workflow(
            self, wf_id, name, description, tags, is_archived, actor
        ):
            raise WorkflowNotFoundError("not found")

    request = WorkflowUpdateRequest(
        name="Updated Workflow",
        actor="admin",
    )

    with pytest.raises(HTTPException) as exc_info:
        await update_workflow(workflow_id, request, Repository())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_archive_workflow_returns_archived() -> None:
    """Archive workflow endpoint returns the archived workflow."""
    workflow_id = uuid4()

    class Repository:
        async def archive_workflow(self, wf_id, actor):
            return Workflow(
                id=wf_id,
                name="Test Workflow",
                slug="test-workflow",
                is_archived=True,
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    result = await archive_workflow(workflow_id, Repository(), actor="admin")

    assert result.id == workflow_id
    assert result.is_archived is True


@pytest.mark.asyncio()
async def test_archive_workflow_not_found() -> None:
    """Archive workflow endpoint raises 404 for missing workflow."""
    workflow_id = uuid4()

    class Repository:
        async def archive_workflow(self, wf_id, actor):
            raise WorkflowNotFoundError("not found")

    with pytest.raises(HTTPException) as exc_info:
        await archive_workflow(workflow_id, Repository(), actor="admin")

    assert exc_info.value.status_code == 404


# Test credential scope inference helper


def test_infer_credential_access_public() -> None:
    """Credential access inference returns 'public' for unrestricted scopes."""
    from orcheo_backend.app import _infer_credential_access

    scope = CredentialScope()
    label = _infer_credential_access(scope)

    assert label == "public"


def test_infer_credential_access_private_single_workflow() -> None:
    """Credential access inference returns 'private' for single workflow restriction."""
    from orcheo_backend.app import _infer_credential_access

    scope = CredentialScope(workflow_ids=[uuid4()])
    label = _infer_credential_access(scope)

    assert label == "private"


def test_infer_credential_access_private_single_workspace() -> None:
    """Credential access returns 'private' for single workspace restriction."""
    from orcheo_backend.app import _infer_credential_access

    scope = CredentialScope(workspace_ids=[uuid4()])
    label = _infer_credential_access(scope)

    assert label == "private"


def test_infer_credential_access_private_single_role() -> None:
    """Credential access inference returns 'private' for single role restriction."""
    from orcheo_backend.app import _infer_credential_access

    scope = CredentialScope(roles=["admin"])
    label = _infer_credential_access(scope)

    assert label == "private"


def test_infer_credential_access_shared_multiple_workflows() -> None:
    """Credential access returns 'shared' for multiple workflow restrictions."""
    from orcheo_backend.app import _infer_credential_access

    scope = CredentialScope(workflow_ids=[uuid4(), uuid4()])
    label = _infer_credential_access(scope)

    assert label == "shared"


def test_infer_credential_access_shared_mixed_restrictions() -> None:
    """Credential access inference returns 'shared' for mixed restrictions."""
    from orcheo_backend.app import _infer_credential_access

    scope = CredentialScope(workflow_ids=[uuid4()], roles=["admin"])
    label = _infer_credential_access(scope)

    assert label == "shared"


# Test credential to response helper


def test_credential_to_response_oauth() -> None:
    """Credential to response converts OAuth metadata correctly."""
    from orcheo.models import EncryptionEnvelope
    from orcheo_backend.app import _credential_to_response

    cred_id = uuid4()
    metadata = CredentialMetadata(
        id=cred_id,
        name="Test OAuth Credential",
        provider="slack",
        kind=CredentialKind.OAUTH,
        scope=CredentialScope(),
        encryption=EncryptionEnvelope(
            algorithm="aes-256-gcm",
            key_id="test-key",
            ciphertext="encrypted-data",
        ),
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )

    response = _credential_to_response(metadata)

    assert response.id == str(cred_id)
    assert response.name == "Test OAuth Credential"
    assert response.provider == "slack"
    assert response.kind == "oauth"
    assert response.secret_preview == "oauth-token"
    assert response.access == "public"


def test_credential_to_response_secret() -> None:
    """Credential to response converts secret metadata correctly."""
    from orcheo.models import EncryptionEnvelope
    from orcheo_backend.app import _credential_to_response

    cred_id = uuid4()
    metadata = CredentialMetadata(
        id=cred_id,
        name="Test Secret",
        provider="custom",
        kind=CredentialKind.SECRET,
        scope=CredentialScope(workflow_ids=[uuid4()]),
        encryption=EncryptionEnvelope(
            algorithm="aes-256-gcm",
            key_id="test-key",
            ciphertext="encrypted-data",
        ),
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )

    response = _credential_to_response(metadata)

    assert response.id == str(cred_id)
    assert response.kind == "secret"
    assert response.secret_preview == "••••••••"
    assert response.access == "private"


def test_credential_to_response_without_owner() -> None:
    """Credential to response handles empty audit log."""
    from orcheo.models import EncryptionEnvelope
    from orcheo_backend.app import _credential_to_response

    cred_id = uuid4()
    metadata = CredentialMetadata(
        id=cred_id,
        name="Test Credential",
        provider="slack",
        kind=CredentialKind.OAUTH,
        scope=CredentialScope(),
        encryption=EncryptionEnvelope(
            algorithm="aes-256-gcm",
            key_id="test-key",
            ciphertext="encrypted-data",
        ),
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )

    response = _credential_to_response(metadata)

    assert response.owner is None


# Test workflow version endpoints


@pytest.mark.asyncio()
async def test_create_workflow_version_success() -> None:
    """Create workflow version endpoint creates and returns new version."""
    from orcheo_backend.app import create_workflow_version
    from orcheo_backend.app.schemas import WorkflowVersionCreateRequest

    workflow_id = uuid4()
    version_id = uuid4()

    class Repository:
        async def create_version(self, wf_id, graph, metadata, notes, created_by):
            return WorkflowVersion(
                id=version_id,
                workflow_id=wf_id,
                version=1,
                graph=graph,
                created_by=created_by,
                notes=notes,
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    request = WorkflowVersionCreateRequest(
        graph={"nodes": []},
        metadata={"test": "data"},
        notes="Test version",
        created_by="admin",
    )

    result = await create_workflow_version(workflow_id, request, Repository())

    assert result.id == version_id
    assert result.workflow_id == workflow_id
    assert result.version == 1


@pytest.mark.asyncio()
async def test_create_workflow_version_not_found() -> None:
    """Create workflow version raises 404 for missing workflow."""
    from orcheo_backend.app import create_workflow_version
    from orcheo_backend.app.schemas import WorkflowVersionCreateRequest

    workflow_id = uuid4()

    class Repository:
        async def create_version(self, wf_id, graph, metadata, notes, created_by):
            raise WorkflowNotFoundError("not found")

    request = WorkflowVersionCreateRequest(
        graph={"nodes": []},
        created_by="admin",
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_workflow_version(workflow_id, request, Repository())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_ingest_workflow_version_success() -> None:
    """Ingest workflow version creates version from script."""
    from orcheo_backend.app import ingest_workflow_version
    from orcheo_backend.app.schemas import WorkflowVersionIngestRequest

    workflow_id = uuid4()
    version_id = uuid4()

    class Repository:
        async def create_version(self, wf_id, graph, metadata, notes, created_by):
            return WorkflowVersion(
                id=version_id,
                workflow_id=wf_id,
                version=1,
                graph=graph,
                created_by=created_by,
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    script_code = (
        "from langgraph.graph import StateGraph\n"
        "graph = StateGraph(dict)\n"
        "graph.add_node('test', lambda x: x)"
    )
    request = WorkflowVersionIngestRequest(
        script=script_code,
        entrypoint="graph",
        created_by="admin",
    )

    result = await ingest_workflow_version(workflow_id, request, Repository())

    assert result.id == version_id


@pytest.mark.asyncio()
async def test_ingest_workflow_version_script_error() -> None:
    """Ingest workflow version handles script ingestion errors."""
    from orcheo_backend.app import ingest_workflow_version
    from orcheo_backend.app.schemas import WorkflowVersionIngestRequest

    workflow_id = uuid4()

    class Repository:
        async def create_version(self, wf_id, graph, metadata, notes, created_by):
            pass

    request = WorkflowVersionIngestRequest(
        script="invalid python code {",
        entrypoint="graph",
        created_by="admin",
    )

    with pytest.raises(HTTPException) as exc_info:
        await ingest_workflow_version(workflow_id, request, Repository())

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio()
async def test_ingest_workflow_version_not_found() -> None:
    """Ingest workflow version raises 404 for missing workflow."""
    from orcheo_backend.app import ingest_workflow_version
    from orcheo_backend.app.schemas import WorkflowVersionIngestRequest

    workflow_id = uuid4()

    class Repository:
        async def create_version(self, wf_id, graph, metadata, notes, created_by):
            raise WorkflowNotFoundError("not found")

    script_code = (
        "from langgraph.graph import StateGraph\n"
        "graph = StateGraph(dict)\n"
        "graph.add_node('test', lambda x: x)"
    )
    request = WorkflowVersionIngestRequest(
        script=script_code,
        entrypoint="graph",
        created_by="admin",
    )

    with pytest.raises(HTTPException) as exc_info:
        await ingest_workflow_version(workflow_id, request, Repository())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_list_workflow_versions_success() -> None:
    """List workflow versions endpoint returns versions."""
    from orcheo_backend.app import list_workflow_versions

    workflow_id = uuid4()
    version1_id = uuid4()
    version2_id = uuid4()

    class Repository:
        async def list_versions(self, wf_id):
            return [
                WorkflowVersion(
                    id=version1_id,
                    workflow_id=wf_id,
                    version=1,
                    graph={},
                    created_by="admin",
                    created_at=datetime.now(tz=UTC),
                    updated_at=datetime.now(tz=UTC),
                ),
                WorkflowVersion(
                    id=version2_id,
                    workflow_id=wf_id,
                    version=2,
                    graph={},
                    created_by="admin",
                    created_at=datetime.now(tz=UTC),
                    updated_at=datetime.now(tz=UTC),
                ),
            ]

    result = await list_workflow_versions(workflow_id, Repository())

    assert len(result) == 2
    assert result[0].id == version1_id
    assert result[1].id == version2_id


@pytest.mark.asyncio()
async def test_list_workflow_versions_not_found() -> None:
    """List workflow versions raises 404 for missing workflow."""
    from orcheo_backend.app import list_workflow_versions
    from orcheo_backend.app.repository import WorkflowNotFoundError

    workflow_id = uuid4()

    class Repository:
        async def list_versions(self, wf_id):
            raise WorkflowNotFoundError("not found")

    with pytest.raises(HTTPException) as exc_info:
        await list_workflow_versions(workflow_id, Repository())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_get_workflow_version_success() -> None:
    """Get workflow version endpoint returns specific version."""
    from orcheo_backend.app import get_workflow_version

    workflow_id = uuid4()
    version_id = uuid4()

    class Repository:
        async def get_version_by_number(self, wf_id, version_number):
            return WorkflowVersion(
                id=version_id,
                workflow_id=wf_id,
                version=version_number,
                graph={},
                created_by="admin",
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    result = await get_workflow_version(workflow_id, 1, Repository())

    assert result.id == version_id
    assert result.version == 1


@pytest.mark.asyncio()
async def test_get_workflow_version_workflow_not_found() -> None:
    """Get workflow version raises 404 for missing workflow."""
    from orcheo_backend.app import get_workflow_version
    from orcheo_backend.app.repository import WorkflowNotFoundError

    workflow_id = uuid4()

    class Repository:
        async def get_version_by_number(self, wf_id, version_number):
            raise WorkflowNotFoundError("not found")

    with pytest.raises(HTTPException) as exc_info:
        await get_workflow_version(workflow_id, 1, Repository())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_get_workflow_version_version_not_found() -> None:
    """Get workflow version raises 404 for missing version."""
    from orcheo_backend.app import get_workflow_version
    from orcheo_backend.app.repository import WorkflowVersionNotFoundError

    workflow_id = uuid4()

    class Repository:
        async def get_version_by_number(self, wf_id, version_number):
            raise WorkflowVersionNotFoundError("not found")

    with pytest.raises(HTTPException) as exc_info:
        await get_workflow_version(workflow_id, 1, Repository())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_diff_workflow_versions_success() -> None:
    """Diff workflow versions endpoint returns diff."""
    from orcheo_backend.app import diff_workflow_versions

    workflow_id = uuid4()

    class Diff:
        base_version = 1
        target_version = 2
        diff = ["+ node1", "- node2"]

    class Repository:
        async def diff_versions(self, wf_id, base, target):
            return Diff()

    result = await diff_workflow_versions(workflow_id, 1, 2, Repository())

    assert result.base_version == 1
    assert result.target_version == 2
    assert result.diff == ["+ node1", "- node2"]


@pytest.mark.asyncio()
async def test_diff_workflow_versions_workflow_not_found() -> None:
    """Diff workflow versions raises 404 for missing workflow."""
    from orcheo_backend.app import diff_workflow_versions
    from orcheo_backend.app.repository import WorkflowNotFoundError

    workflow_id = uuid4()

    class Repository:
        async def diff_versions(self, wf_id, base, target):
            raise WorkflowNotFoundError("not found")

    with pytest.raises(HTTPException) as exc_info:
        await diff_workflow_versions(workflow_id, 1, 2, Repository())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_diff_workflow_versions_version_not_found() -> None:
    """Diff workflow versions raises 404 for missing version."""
    from orcheo_backend.app import diff_workflow_versions
    from orcheo_backend.app.repository import WorkflowVersionNotFoundError

    workflow_id = uuid4()

    class Repository:
        async def diff_versions(self, wf_id, base, target):
            raise WorkflowVersionNotFoundError("not found")

    with pytest.raises(HTTPException) as exc_info:
        await diff_workflow_versions(workflow_id, 1, 2, Repository())

    assert exc_info.value.status_code == 404


# Test workflow run endpoints


@pytest.mark.asyncio()
async def test_create_workflow_run_success() -> None:
    """Create workflow run endpoint creates and returns new run."""
    from orcheo_backend.app import create_workflow_run
    from orcheo_backend.app.schemas import WorkflowRunCreateRequest

    workflow_id = uuid4()
    run_id = uuid4()
    version_id = uuid4()

    class Repository:
        async def create_run(
            self, wf_id, workflow_version_id, triggered_by, input_payload
        ):
            return WorkflowRun(
                id=run_id,
                workflow_version_id=workflow_version_id,
                triggered_by=triggered_by,
                input_payload=input_payload,
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    request = WorkflowRunCreateRequest(
        workflow_version_id=version_id,
        triggered_by="user@example.com",
        input_payload={"key": "value"},
    )

    result = await create_workflow_run(workflow_id, request, Repository(), None)

    assert result.id == run_id
    assert result.triggered_by == "user@example.com"


@pytest.mark.asyncio()
async def test_create_workflow_run_workflow_not_found() -> None:
    """Create workflow run raises 404 for missing workflow."""
    from orcheo_backend.app import create_workflow_run
    from orcheo_backend.app.repository import WorkflowNotFoundError
    from orcheo_backend.app.schemas import WorkflowRunCreateRequest

    workflow_id = uuid4()
    version_id = uuid4()

    class Repository:
        async def create_run(
            self, wf_id, workflow_version_id, triggered_by, input_payload
        ):
            raise WorkflowNotFoundError("not found")

    request = WorkflowRunCreateRequest(
        workflow_version_id=version_id,
        triggered_by="user@example.com",
        input_payload={},
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_workflow_run(workflow_id, request, Repository(), None)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_create_workflow_run_version_not_found() -> None:
    """Create workflow run raises 404 for missing version."""
    from orcheo_backend.app import create_workflow_run
    from orcheo_backend.app.repository import WorkflowVersionNotFoundError
    from orcheo_backend.app.schemas import WorkflowRunCreateRequest

    workflow_id = uuid4()
    version_id = uuid4()

    class Repository:
        async def create_run(
            self, wf_id, workflow_version_id, triggered_by, input_payload
        ):
            raise WorkflowVersionNotFoundError("not found")

    request = WorkflowRunCreateRequest(
        workflow_version_id=version_id,
        triggered_by="user@example.com",
        input_payload={},
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_workflow_run(workflow_id, request, Repository(), None)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_create_workflow_run_credential_health_error() -> None:
    """Create workflow run handles credential health errors."""
    from orcheo_backend.app import create_workflow_run
    from orcheo_backend.app.schemas import WorkflowRunCreateRequest

    workflow_id = uuid4()
    version_id = uuid4()

    class Repository:
        async def create_run(
            self, wf_id, workflow_version_id, triggered_by, input_payload
        ):
            raise _health_error(wf_id)

    request = WorkflowRunCreateRequest(
        workflow_version_id=version_id,
        triggered_by="user@example.com",
        input_payload={},
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_workflow_run(workflow_id, request, Repository(), None)

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio()
async def test_list_workflow_runs_success() -> None:
    """List workflow runs endpoint returns runs."""
    from orcheo_backend.app import list_workflow_runs

    workflow_id = uuid4()
    run1_id = uuid4()
    run2_id = uuid4()
    version_id = uuid4()

    class Repository:
        async def list_runs_for_workflow(self, wf_id):
            return [
                WorkflowRun(
                    id=run1_id,
                    workflow_version_id=version_id,
                    triggered_by="user1",
                    input_payload={},
                    created_at=datetime.now(tz=UTC),
                    updated_at=datetime.now(tz=UTC),
                ),
                WorkflowRun(
                    id=run2_id,
                    workflow_version_id=version_id,
                    triggered_by="user2",
                    input_payload={},
                    created_at=datetime.now(tz=UTC),
                    updated_at=datetime.now(tz=UTC),
                ),
            ]

    result = await list_workflow_runs(workflow_id, Repository())

    assert len(result) == 2
    assert result[0].id == run1_id
    assert result[1].id == run2_id


@pytest.mark.asyncio()
async def test_list_workflow_runs_not_found() -> None:
    """List workflow runs raises 404 for missing workflow."""
    from orcheo_backend.app import list_workflow_runs
    from orcheo_backend.app.repository import WorkflowNotFoundError

    workflow_id = uuid4()

    class Repository:
        async def list_runs_for_workflow(self, wf_id):
            raise WorkflowNotFoundError("not found")

    with pytest.raises(HTTPException) as exc_info:
        await list_workflow_runs(workflow_id, Repository())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_get_workflow_run_success() -> None:
    """Get workflow run endpoint returns specific run."""
    from orcheo_backend.app import get_workflow_run

    run_id = uuid4()
    version_id = uuid4()

    class Repository:
        async def get_run(self, run_id):
            return WorkflowRun(
                id=run_id,
                workflow_version_id=version_id,
                triggered_by="user",
                input_payload={},
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    result = await get_workflow_run(run_id, Repository())

    assert result.id == run_id


@pytest.mark.asyncio()
async def test_get_workflow_run_not_found() -> None:
    """Get workflow run raises 404 for missing run."""
    from orcheo_backend.app import get_workflow_run
    from orcheo_backend.app.repository import WorkflowRunNotFoundError

    run_id = uuid4()

    class Repository:
        async def get_run(self, run_id):
            raise WorkflowRunNotFoundError("not found")

    with pytest.raises(HTTPException) as exc_info:
        await get_workflow_run(run_id, Repository())

    assert exc_info.value.status_code == 404


# Test execution history endpoints


@pytest.mark.asyncio()
async def test_get_execution_history_success() -> None:
    """Get execution history endpoint returns history."""
    from orcheo_backend.app import get_execution_history

    execution_id = "test-exec-123"

    class HistoryStore:
        async def get_history(self, exec_id):
            return RunHistoryRecord(
                workflow_id=str(uuid4()),
                execution_id=exec_id,
                inputs={"test": "data"},
            )

    result = await get_execution_history(execution_id, HistoryStore())

    assert result.execution_id == execution_id


@pytest.mark.asyncio()
async def test_get_execution_history_not_found() -> None:
    """Get execution history raises 404 for missing execution."""
    from orcheo_backend.app import get_execution_history
    from orcheo_backend.app.history import RunHistoryNotFoundError

    execution_id = "missing-exec"

    class HistoryStore:
        async def get_history(self, exec_id):
            raise RunHistoryNotFoundError("not found")

    with pytest.raises(HTTPException) as exc_info:
        await get_execution_history(execution_id, HistoryStore())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_replay_execution_success() -> None:
    """Replay execution endpoint returns sliced history."""
    from orcheo_backend.app import replay_execution
    from orcheo_backend.app.history import RunHistoryStep
    from orcheo_backend.app.schemas import RunReplayRequest

    execution_id = "test-exec-123"

    class HistoryStore:
        async def get_history(self, exec_id):
            record = RunHistoryRecord(
                workflow_id=str(uuid4()),
                execution_id=exec_id,
                inputs={"test": "data"},
            )
            record.steps = [
                RunHistoryStep(index=0, payload={"step": 1}),
                RunHistoryStep(index=1, payload={"step": 2}),
                RunHistoryStep(index=2, payload={"step": 3}),
            ]
            return record

    request = RunReplayRequest(from_step=1)
    result = await replay_execution(execution_id, request, HistoryStore())

    assert result.execution_id == execution_id
    assert len(result.steps) == 2
    assert result.steps[0].index == 1


@pytest.mark.asyncio()
async def test_replay_execution_not_found() -> None:
    """Replay execution raises 404 for missing execution."""
    from orcheo_backend.app import replay_execution
    from orcheo_backend.app.history import RunHistoryNotFoundError
    from orcheo_backend.app.schemas import RunReplayRequest

    execution_id = "missing-exec"

    class HistoryStore:
        async def get_history(self, exec_id):
            raise RunHistoryNotFoundError("not found")

    request = RunReplayRequest(from_step=0)

    with pytest.raises(HTTPException) as exc_info:
        await replay_execution(execution_id, request, HistoryStore())

    assert exc_info.value.status_code == 404


# Test credential endpoints


def test_list_credentials_success() -> None:
    """List credentials endpoint returns credentials."""
    from orcheo.models import EncryptionEnvelope
    from orcheo_backend.app import list_credentials

    cred1_id = uuid4()
    cred2_id = uuid4()

    class Vault:
        def list_credentials(self, context=None):
            return [
                CredentialMetadata(
                    id=cred1_id,
                    name="Cred 1",
                    provider="slack",
                    kind=CredentialKind.OAUTH,
                    scope=CredentialScope(),
                    encryption=EncryptionEnvelope(
                        algorithm="aes-256-gcm",
                        key_id="test-key",
                        ciphertext="encrypted",
                    ),
                    created_at=datetime.now(tz=UTC),
                    updated_at=datetime.now(tz=UTC),
                ),
                CredentialMetadata(
                    id=cred2_id,
                    name="Cred 2",
                    provider="github",
                    kind=CredentialKind.SECRET,
                    scope=CredentialScope(),
                    encryption=EncryptionEnvelope(
                        algorithm="aes-256-gcm",
                        key_id="test-key",
                        ciphertext="encrypted",
                    ),
                    created_at=datetime.now(tz=UTC),
                    updated_at=datetime.now(tz=UTC),
                ),
            ]

    result = list_credentials(Vault())

    assert len(result) == 2
    assert result[0].id == str(cred1_id)
    assert result[1].id == str(cred2_id)


def test_list_credentials_with_workflow_context() -> None:
    """List credentials uses workflow context for filtering."""
    from orcheo_backend.app import list_credentials

    workflow_id = uuid4()
    context_received = None

    class Vault:
        def list_credentials(self, context=None):
            nonlocal context_received
            context_received = context
            return []

    list_credentials(Vault(), workflow_id=workflow_id)

    assert context_received is not None
    assert context_received.workflow_id == workflow_id


def test_create_credential_success() -> None:
    """Create credential endpoint creates and returns credential."""
    from orcheo.models import EncryptionEnvelope
    from orcheo_backend.app import create_credential
    from orcheo_backend.app.schemas import CredentialCreateRequest

    cred_id = uuid4()

    class Vault:
        def create_credential(self, name, provider, scopes, secret, actor, scope, kind):
            return CredentialMetadata(
                id=cred_id,
                name=name,
                provider=provider,
                kind=kind,
                scope=scope or CredentialScope(),
                encryption=EncryptionEnvelope(
                    algorithm="aes-256-gcm",
                    key_id="test-key",
                    ciphertext="encrypted",
                ),
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    request = CredentialCreateRequest(
        name="Test Cred",
        provider="slack",
        scopes=["chat:write"],
        secret="test-secret",
        actor="user",
        access="public",
        kind=CredentialKind.SECRET,
    )

    result = create_credential(request, Vault())

    assert result.id == str(cred_id)
    assert result.name == "Test Cred"


def test_create_credential_validation_error() -> None:
    """Create credential handles validation errors."""
    from orcheo_backend.app import create_credential
    from orcheo_backend.app.schemas import CredentialCreateRequest

    class Vault:
        def create_credential(self, name, provider, scopes, secret, actor, scope, kind):
            raise ValueError("Invalid credential")

    request = CredentialCreateRequest(
        name="Test Cred",
        provider="slack",
        scopes=[],
        secret="test-secret",
        actor="user",
        access="public",
        kind=CredentialKind.SECRET,
    )

    with pytest.raises(HTTPException) as exc_info:
        create_credential(request, Vault())

    assert exc_info.value.status_code == 422


def test_create_credential_access_override() -> None:
    """Create credential overrides access when request differs from inferred."""
    from orcheo.models import EncryptionEnvelope
    from orcheo_backend.app import create_credential
    from orcheo_backend.app.schemas import CredentialCreateRequest

    cred_id = uuid4()
    workflow_id = uuid4()

    class Vault:
        def create_credential(self, name, provider, scopes, secret, actor, scope, kind):
            # Return credential with workflow scope (would be "private")
            return CredentialMetadata(
                id=cred_id,
                name=name,
                provider=provider,
                kind=kind,
                scope=CredentialScope(workflow_ids=[workflow_id]),
                encryption=EncryptionEnvelope(
                    algorithm="aes-256-gcm",
                    key_id="test-key",
                    ciphertext="encrypted",
                ),
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    # Request with "shared" access but vault will create "private"
    request = CredentialCreateRequest(
        name="Test Cred",
        provider="slack",
        scopes=["chat:write"],
        secret="test-secret",
        actor="user",
        access="shared",
        kind=CredentialKind.SECRET,
    )

    result = create_credential(request, Vault())

    # Response should use the requested access, not the inferred one
    assert result.access == "shared"


def test_delete_credential_success() -> None:
    """Delete credential endpoint deletes credential."""
    from orcheo_backend.app import delete_credential

    cred_id = uuid4()
    deleted_id = None

    class Vault:
        def delete_credential(self, credential_id, context=None):
            nonlocal deleted_id
            deleted_id = credential_id

    response = delete_credential(cred_id, Vault())

    assert response.status_code == 204
    assert deleted_id == cred_id


def test_delete_credential_not_found() -> None:
    """Delete credential raises 404 for missing credential."""
    from orcheo.vault import CredentialNotFoundError
    from orcheo_backend.app import delete_credential

    cred_id = uuid4()

    class Vault:
        def delete_credential(self, credential_id, context=None):
            raise CredentialNotFoundError("not found")

    with pytest.raises(HTTPException) as exc_info:
        delete_credential(cred_id, Vault())

    assert exc_info.value.status_code == 404


def test_delete_credential_scope_error() -> None:
    """Delete credential raises 403 for scope violations."""
    from orcheo_backend.app import delete_credential

    cred_id = uuid4()

    class Vault:
        def delete_credential(self, credential_id, context=None):
            raise WorkflowScopeError("Access denied")

    with pytest.raises(HTTPException) as exc_info:
        delete_credential(cred_id, Vault())

    assert exc_info.value.status_code == 403


# Test helper functions


def test_scope_from_access_private() -> None:
    """_scope_from_access returns workflow scope for private access."""
    from orcheo_backend.app import _scope_from_access

    workflow_id = uuid4()
    scope = _scope_from_access("private", workflow_id)

    assert scope is not None
    assert workflow_id in scope.workflow_ids


def test_scope_from_access_shared_with_workflow() -> None:
    """_scope_from_access returns workflow scope for shared with workflow."""
    from orcheo_backend.app import _scope_from_access

    workflow_id = uuid4()
    scope = _scope_from_access("shared", workflow_id)

    assert scope is not None
    assert workflow_id in scope.workflow_ids


def test_scope_from_access_shared_without_workflow() -> None:
    """_scope_from_access returns unrestricted for shared without workflow."""
    from orcheo_backend.app import _scope_from_access

    scope = _scope_from_access("shared", None)

    assert scope is not None
    assert scope.is_unrestricted()


def test_scope_from_access_public() -> None:
    """_scope_from_access returns unrestricted scope for public access."""
    from orcheo_backend.app import _scope_from_access

    scope = _scope_from_access("public", None)

    assert scope is not None
    assert scope.is_unrestricted()


def test_context_from_workflow_with_id() -> None:
    """_context_from_workflow creates context with workflow ID."""
    from orcheo_backend.app import _context_from_workflow

    workflow_id = uuid4()
    context = _context_from_workflow(workflow_id)

    assert context is not None
    assert context.workflow_id == workflow_id


def test_context_from_workflow_without_id() -> None:
    """_context_from_workflow returns None without workflow ID."""
    from orcheo_backend.app import _context_from_workflow

    context = _context_from_workflow(None)

    assert context is None


def test_history_to_response_with_steps() -> None:
    """_history_to_response converts record with steps to response."""
    from orcheo_backend.app import _history_to_response
    from orcheo_backend.app.history import RunHistoryStep

    record = RunHistoryRecord(
        workflow_id=str(uuid4()),
        execution_id="test-exec",
        inputs={"key": "value"},
    )
    record.steps = [
        RunHistoryStep(index=0, payload={"step": 1}),
        RunHistoryStep(index=1, payload={"step": 2}),
    ]

    response = _history_to_response(record)

    assert response.execution_id == "test-exec"
    assert len(response.steps) == 2


def test_history_to_response_with_from_step() -> None:
    """_history_to_response slices steps from given index."""
    from orcheo_backend.app import _history_to_response
    from orcheo_backend.app.history import RunHistoryStep

    record = RunHistoryRecord(
        workflow_id=str(uuid4()),
        execution_id="test-exec",
        inputs={},
    )
    record.steps = [
        RunHistoryStep(index=0, payload={"step": 1}),
        RunHistoryStep(index=1, payload={"step": 2}),
        RunHistoryStep(index=2, payload={"step": 3}),
    ]

    response = _history_to_response(record, from_step=1)

    assert len(response.steps) == 2
    assert response.steps[0].index == 1


def test_health_report_to_response() -> None:
    """_health_report_to_response converts report to response."""
    from orcheo_backend.app import _health_report_to_response

    workflow_id = uuid4()
    cred_id = uuid4()

    report = CredentialHealthReport(
        workflow_id=workflow_id,
        results=[
            CredentialHealthResult(
                credential_id=cred_id,
                name="Test Cred",
                provider="slack",
                status=CredentialHealthStatus.HEALTHY,
                last_checked_at=datetime.now(tz=UTC),
                failure_reason=None,
            )
        ],
        checked_at=datetime.now(tz=UTC),
    )

    response = _health_report_to_response(report)

    assert response.workflow_id == str(workflow_id)
    assert response.status == CredentialHealthStatus.HEALTHY
    assert len(response.credentials) == 1


def test_health_report_to_response_unhealthy() -> None:
    """_health_report_to_response marks unhealthy reports."""
    from orcheo_backend.app import _health_report_to_response

    workflow_id = uuid4()
    cred_id = uuid4()

    report = CredentialHealthReport(
        workflow_id=workflow_id,
        results=[
            CredentialHealthResult(
                credential_id=cred_id,
                name="Test Cred",
                provider="slack",
                status=CredentialHealthStatus.UNHEALTHY,
                last_checked_at=datetime.now(tz=UTC),
                failure_reason="Token expired",
            )
        ],
        checked_at=datetime.now(tz=UTC),
    )

    response = _health_report_to_response(report)

    assert response.status == CredentialHealthStatus.UNHEALTHY
    assert response.credentials[0].failure_reason == "Token expired"


# Test workflow run state transitions


@pytest.mark.asyncio()
async def test_mark_run_started_success() -> None:
    """Mark run started endpoint transitions run to running state."""
    from orcheo_backend.app import mark_run_started
    from orcheo_backend.app.schemas import RunActionRequest

    run_id = uuid4()
    version_id = uuid4()

    class Repository:
        async def mark_run_started(self, run_id, actor):
            return WorkflowRun(
                id=run_id,
                workflow_version_id=version_id,
                triggered_by="user",
                input_payload={},
                status="running",
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    request = RunActionRequest(actor="system")
    result = await mark_run_started(run_id, request, Repository())

    assert result.id == run_id
    assert result.status == "running"


@pytest.mark.asyncio()
async def test_mark_run_started_not_found() -> None:
    """Mark run started raises 404 for missing run."""
    from orcheo_backend.app import mark_run_started
    from orcheo_backend.app.repository import WorkflowRunNotFoundError
    from orcheo_backend.app.schemas import RunActionRequest

    run_id = uuid4()

    class Repository:
        async def mark_run_started(self, run_id, actor):
            raise WorkflowRunNotFoundError("not found")

    request = RunActionRequest(actor="system")

    with pytest.raises(HTTPException) as exc_info:
        await mark_run_started(run_id, request, Repository())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_mark_run_started_conflict() -> None:
    """Mark run started raises 409 for invalid state transition."""
    from orcheo_backend.app import mark_run_started
    from orcheo_backend.app.schemas import RunActionRequest

    run_id = uuid4()

    class Repository:
        async def mark_run_started(self, run_id, actor):
            raise ValueError("Invalid state transition")

    request = RunActionRequest(actor="system")

    with pytest.raises(HTTPException) as exc_info:
        await mark_run_started(run_id, request, Repository())

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio()
async def test_mark_run_succeeded_success() -> None:
    """Mark run succeeded endpoint marks run as successful."""
    from orcheo_backend.app import mark_run_succeeded
    from orcheo_backend.app.schemas import RunSucceedRequest

    run_id = uuid4()
    version_id = uuid4()

    class Repository:
        async def mark_run_succeeded(self, run_id, actor, output):
            return WorkflowRun(
                id=run_id,
                workflow_version_id=version_id,
                triggered_by="user",
                input_payload={},
                output_payload=output,
                status="succeeded",
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    request = RunSucceedRequest(actor="system", output={"result": "ok"})
    result = await mark_run_succeeded(run_id, request, Repository())

    assert result.id == run_id
    assert result.status == "succeeded"


@pytest.mark.asyncio()
async def test_mark_run_succeeded_not_found() -> None:
    """Mark run succeeded raises 404 for missing run."""
    from orcheo_backend.app import mark_run_succeeded
    from orcheo_backend.app.repository import WorkflowRunNotFoundError
    from orcheo_backend.app.schemas import RunSucceedRequest

    run_id = uuid4()

    class Repository:
        async def mark_run_succeeded(self, run_id, actor, output):
            raise WorkflowRunNotFoundError("not found")

    request = RunSucceedRequest(actor="system")

    with pytest.raises(HTTPException) as exc_info:
        await mark_run_succeeded(run_id, request, Repository())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_mark_run_succeeded_conflict() -> None:
    """Mark run succeeded raises 409 for invalid state transition."""
    from orcheo_backend.app import mark_run_succeeded
    from orcheo_backend.app.schemas import RunSucceedRequest

    run_id = uuid4()

    class Repository:
        async def mark_run_succeeded(self, run_id, actor, output):
            raise ValueError("Invalid state transition")

    request = RunSucceedRequest(actor="system")

    with pytest.raises(HTTPException) as exc_info:
        await mark_run_succeeded(run_id, request, Repository())

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio()
async def test_mark_run_failed_success() -> None:
    """Mark run failed endpoint marks run as failed."""
    from orcheo_backend.app import mark_run_failed
    from orcheo_backend.app.schemas import RunFailRequest

    run_id = uuid4()
    version_id = uuid4()

    class Repository:
        async def mark_run_failed(self, run_id, actor, error):
            return WorkflowRun(
                id=run_id,
                workflow_version_id=version_id,
                triggered_by="user",
                input_payload={},
                error=error,
                status="failed",
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    request = RunFailRequest(actor="system", error="Test error")
    result = await mark_run_failed(run_id, request, Repository())

    assert result.id == run_id
    assert result.status == "failed"


@pytest.mark.asyncio()
async def test_mark_run_failed_not_found() -> None:
    """Mark run failed raises 404 for missing run."""
    from orcheo_backend.app import mark_run_failed
    from orcheo_backend.app.repository import WorkflowRunNotFoundError
    from orcheo_backend.app.schemas import RunFailRequest

    run_id = uuid4()

    class Repository:
        async def mark_run_failed(self, run_id, actor, error):
            raise WorkflowRunNotFoundError("not found")

    request = RunFailRequest(actor="system", error="Test error")

    with pytest.raises(HTTPException) as exc_info:
        await mark_run_failed(run_id, request, Repository())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_mark_run_failed_conflict() -> None:
    """Mark run failed raises 409 for invalid state transition."""
    from orcheo_backend.app import mark_run_failed
    from orcheo_backend.app.schemas import RunFailRequest

    run_id = uuid4()

    class Repository:
        async def mark_run_failed(self, run_id, actor, error):
            raise ValueError("Invalid state transition")

    request = RunFailRequest(actor="system", error="Test error")

    with pytest.raises(HTTPException) as exc_info:
        await mark_run_failed(run_id, request, Repository())

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio()
async def test_mark_run_cancelled_success() -> None:
    """Mark run cancelled endpoint cancels run."""
    from orcheo_backend.app import mark_run_cancelled
    from orcheo_backend.app.schemas import RunCancelRequest

    run_id = uuid4()
    version_id = uuid4()

    class Repository:
        async def mark_run_cancelled(self, run_id, actor, reason):
            return WorkflowRun(
                id=run_id,
                workflow_version_id=version_id,
                triggered_by="user",
                input_payload={},
                status="cancelled",
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    request = RunCancelRequest(actor="system", reason="User requested")
    result = await mark_run_cancelled(run_id, request, Repository())

    assert result.id == run_id
    assert result.status == "cancelled"


@pytest.mark.asyncio()
async def test_mark_run_cancelled_not_found() -> None:
    """Mark run cancelled raises 404 for missing run."""
    from orcheo_backend.app import mark_run_cancelled
    from orcheo_backend.app.repository import WorkflowRunNotFoundError
    from orcheo_backend.app.schemas import RunCancelRequest

    run_id = uuid4()

    class Repository:
        async def mark_run_cancelled(self, run_id, actor, reason):
            raise WorkflowRunNotFoundError("not found")

    request = RunCancelRequest(actor="system")

    with pytest.raises(HTTPException) as exc_info:
        await mark_run_cancelled(run_id, request, Repository())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_mark_run_cancelled_conflict() -> None:
    """Mark run cancelled raises 409 for invalid state transition."""
    from orcheo_backend.app import mark_run_cancelled
    from orcheo_backend.app.schemas import RunCancelRequest

    run_id = uuid4()

    class Repository:
        async def mark_run_cancelled(self, run_id, actor, reason):
            raise ValueError("Invalid state transition")

    request = RunCancelRequest(actor="system")

    with pytest.raises(HTTPException) as exc_info:
        await mark_run_cancelled(run_id, request, Repository())

    assert exc_info.value.status_code == 409


# Test credential template endpoints


def test_list_credential_templates_success() -> None:
    """List credential templates endpoint returns templates."""
    from orcheo.models import CredentialIssuancePolicy, CredentialTemplate
    from orcheo_backend.app import list_credential_templates

    template1_id = uuid4()
    template2_id = uuid4()

    class Vault:
        def list_templates(self, context=None):
            return [
                CredentialTemplate(
                    id=template1_id,
                    name="Template 1",
                    provider="slack",
                    scopes=["chat:write"],
                    kind=CredentialKind.OAUTH,
                    scope=CredentialScope(),
                    issuance_policy=CredentialIssuancePolicy(),
                    created_at=datetime.now(tz=UTC),
                    updated_at=datetime.now(tz=UTC),
                ),
                CredentialTemplate(
                    id=template2_id,
                    name="Template 2",
                    provider="github",
                    scopes=["repo"],
                    kind=CredentialKind.OAUTH,
                    scope=CredentialScope(),
                    issuance_policy=CredentialIssuancePolicy(),
                    created_at=datetime.now(tz=UTC),
                    updated_at=datetime.now(tz=UTC),
                ),
            ]

    result = list_credential_templates(Vault())

    assert len(result) == 2
    assert result[0].id == str(template1_id)
    assert result[1].id == str(template2_id)


def test_create_credential_template_success() -> None:
    """Create credential template endpoint creates template."""
    from orcheo.models import CredentialIssuancePolicy, CredentialTemplate
    from orcheo_backend.app import create_credential_template
    from orcheo_backend.app.schemas import CredentialTemplateCreateRequest

    template_id = uuid4()

    class Vault:
        def create_template(
            self,
            name,
            provider,
            scopes,
            actor,
            description,
            scope,
            kind,
            issuance_policy,
        ):
            return CredentialTemplate(
                id=template_id,
                name=name,
                provider=provider,
                scopes=scopes,
                kind=kind,
                scope=scope or CredentialScope(),
                issuance_policy=issuance_policy or CredentialIssuancePolicy(),
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    request = CredentialTemplateCreateRequest(
        name="Test Template",
        provider="slack",
        scopes=["chat:write"],
        actor="admin",
        kind=CredentialKind.OAUTH,
    )

    result = create_credential_template(request, Vault())

    assert result.id == str(template_id)
    assert result.name == "Test Template"


def test_get_credential_template_success() -> None:
    """Get credential template endpoint returns template."""
    from orcheo.models import CredentialIssuancePolicy, CredentialTemplate
    from orcheo_backend.app import get_credential_template

    template_id = uuid4()

    class Vault:
        def get_template(self, template_id, context=None):
            return CredentialTemplate(
                id=template_id,
                name="Test Template",
                provider="slack",
                scopes=["chat:write"],
                kind=CredentialKind.OAUTH,
                scope=CredentialScope(),
                issuance_policy=CredentialIssuancePolicy(),
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    result = get_credential_template(template_id, Vault())

    assert result.id == str(template_id)


def test_get_credential_template_not_found() -> None:
    """Get credential template raises 404 for missing template."""
    from orcheo.vault import CredentialTemplateNotFoundError
    from orcheo_backend.app import get_credential_template

    template_id = uuid4()

    class Vault:
        def get_template(self, template_id, context=None):
            raise CredentialTemplateNotFoundError("not found")

    with pytest.raises(HTTPException) as exc_info:
        get_credential_template(template_id, Vault())

    assert exc_info.value.status_code == 404


def test_get_credential_template_scope_error() -> None:
    """Get credential template raises 403 for scope violations."""
    from orcheo_backend.app import get_credential_template

    template_id = uuid4()

    class Vault:
        def get_template(self, template_id, context=None):
            raise WorkflowScopeError("Access denied")

    with pytest.raises(HTTPException) as exc_info:
        get_credential_template(template_id, Vault())

    assert exc_info.value.status_code == 403


def test_update_credential_template_success() -> None:
    """Update credential template endpoint updates template."""
    from orcheo.models import CredentialIssuancePolicy, CredentialTemplate
    from orcheo_backend.app import update_credential_template
    from orcheo_backend.app.schemas import CredentialTemplateUpdateRequest

    template_id = uuid4()

    class Vault:
        def update_template(
            self,
            template_id,
            actor,
            name,
            scopes,
            description,
            scope,
            kind,
            issuance_policy,
            context,
        ):
            return CredentialTemplate(
                id=template_id,
                name=name or "Updated Template",
                provider="slack",
                scopes=scopes or ["chat:write"],
                kind=kind or CredentialKind.OAUTH,
                scope=scope or CredentialScope(),
                issuance_policy=issuance_policy or CredentialIssuancePolicy(),
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    request = CredentialTemplateUpdateRequest(
        actor="admin",
        name="Updated Template",
    )

    result = update_credential_template(template_id, request, Vault())

    assert result.id == str(template_id)
    assert result.name == "Updated Template"


def test_update_credential_template_not_found() -> None:
    """Update credential template raises 404 for missing template."""
    from orcheo.vault import CredentialTemplateNotFoundError
    from orcheo_backend.app import update_credential_template
    from orcheo_backend.app.schemas import CredentialTemplateUpdateRequest

    template_id = uuid4()

    class Vault:
        def update_template(
            self,
            template_id,
            actor,
            name,
            scopes,
            description,
            scope,
            kind,
            issuance_policy,
            context,
        ):
            raise CredentialTemplateNotFoundError("not found")

    request = CredentialTemplateUpdateRequest(actor="admin")

    with pytest.raises(HTTPException) as exc_info:
        update_credential_template(template_id, request, Vault())

    assert exc_info.value.status_code == 404


def test_update_credential_template_scope_error() -> None:
    """Update credential template raises 403 for scope violations."""
    from orcheo_backend.app import update_credential_template
    from orcheo_backend.app.schemas import CredentialTemplateUpdateRequest

    template_id = uuid4()

    class Vault:
        def update_template(
            self,
            template_id,
            actor,
            name,
            scopes,
            description,
            scope,
            kind,
            issuance_policy,
            context,
        ):
            raise WorkflowScopeError("Access denied")

    request = CredentialTemplateUpdateRequest(actor="admin")

    with pytest.raises(HTTPException) as exc_info:
        update_credential_template(template_id, request, Vault())

    assert exc_info.value.status_code == 403


def test_delete_credential_template_success() -> None:
    """Delete credential template endpoint deletes template."""
    from orcheo_backend.app import delete_credential_template

    template_id = uuid4()
    deleted_id = None

    class Vault:
        def delete_template(self, template_id, context=None):
            nonlocal deleted_id
            deleted_id = template_id

    response = delete_credential_template(template_id, Vault())

    assert response.status_code == 204
    assert deleted_id == template_id


def test_delete_credential_template_not_found() -> None:
    """Delete credential template raises 404 for missing template."""
    from orcheo.vault import CredentialTemplateNotFoundError
    from orcheo_backend.app import delete_credential_template

    template_id = uuid4()

    class Vault:
        def delete_template(self, template_id, context=None):
            raise CredentialTemplateNotFoundError("not found")

    with pytest.raises(HTTPException) as exc_info:
        delete_credential_template(template_id, Vault())

    assert exc_info.value.status_code == 404


def test_delete_credential_template_scope_error() -> None:
    """Delete credential template raises 403 for scope violations."""
    from orcheo_backend.app import delete_credential_template

    template_id = uuid4()

    class Vault:
        def delete_template(self, template_id, context=None):
            raise WorkflowScopeError("Access denied")

    with pytest.raises(HTTPException) as exc_info:
        delete_credential_template(template_id, Vault())

    assert exc_info.value.status_code == 403


def test_issue_credential_from_template_success() -> None:
    """Issue credential from template endpoint creates credential."""
    from orcheo.models import EncryptionEnvelope
    from orcheo_backend.app import issue_credential_from_template
    from orcheo_backend.app.schemas import CredentialIssuanceRequest

    template_id = uuid4()
    cred_id = uuid4()

    class Service:
        def issue_from_template(
            self,
            template_id,
            secret,
            actor,
            name,
            scopes,
            context,
            oauth_tokens,
        ):
            return CredentialMetadata(
                id=cred_id,
                name=name or "Issued Credential",
                provider="slack",
                kind=CredentialKind.OAUTH,
                scope=CredentialScope(),
                template_id=template_id,
                encryption=EncryptionEnvelope(
                    algorithm="aes-256-gcm",
                    key_id="test-key",
                    ciphertext="encrypted",
                ),
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    request = CredentialIssuanceRequest(
        template_id=template_id,
        actor="admin",
        name="Issued Credential",
        secret="test-secret",
    )

    result = issue_credential_from_template(template_id, request, Service())

    assert result.credential_id == str(cred_id)
    assert result.template_id == str(template_id)


def test_issue_credential_from_template_not_configured() -> None:
    """Issue credential requires configured service."""
    from orcheo_backend.app import issue_credential_from_template
    from orcheo_backend.app.schemas import CredentialIssuanceRequest

    template_id = uuid4()

    request = CredentialIssuanceRequest(
        template_id=template_id,
        actor="admin",
        secret="test-secret",
    )

    with pytest.raises(HTTPException) as exc_info:
        issue_credential_from_template(template_id, request, None)

    assert exc_info.value.status_code == 503


def test_issue_credential_from_template_not_found() -> None:
    """Issue credential raises 404 for missing template."""
    from orcheo.vault import CredentialTemplateNotFoundError
    from orcheo_backend.app import issue_credential_from_template
    from orcheo_backend.app.schemas import CredentialIssuanceRequest

    template_id = uuid4()

    class Service:
        def issue_from_template(
            self,
            template_id,
            secret,
            actor,
            name,
            scopes,
            context,
            oauth_tokens,
        ):
            raise CredentialTemplateNotFoundError("not found")

    request = CredentialIssuanceRequest(
        template_id=template_id,
        actor="admin",
        secret="test-secret",
    )

    with pytest.raises(HTTPException) as exc_info:
        issue_credential_from_template(template_id, request, Service())

    assert exc_info.value.status_code == 404


def test_issue_credential_from_template_scope_error() -> None:
    """Issue credential raises 403 for scope violations."""
    from orcheo_backend.app import issue_credential_from_template
    from orcheo_backend.app.schemas import CredentialIssuanceRequest

    template_id = uuid4()

    class Service:
        def issue_from_template(
            self,
            template_id,
            secret,
            actor,
            name,
            scopes,
            context,
            oauth_tokens,
        ):
            raise WorkflowScopeError("Access denied")

    request = CredentialIssuanceRequest(
        template_id=template_id,
        actor="admin",
        secret="test-secret",
    )

    with pytest.raises(HTTPException) as exc_info:
        issue_credential_from_template(template_id, request, Service())

    assert exc_info.value.status_code == 403


def test_issue_credential_from_template_validation_error() -> None:
    """Issue credential raises 400 for validation errors."""
    from orcheo_backend.app import issue_credential_from_template
    from orcheo_backend.app.schemas import CredentialIssuanceRequest

    template_id = uuid4()

    class Service:
        def issue_from_template(
            self,
            template_id,
            secret,
            actor,
            name,
            scopes,
            context,
            oauth_tokens,
        ):
            raise ValueError("Invalid secret format")

    request = CredentialIssuanceRequest(
        template_id=template_id,
        actor="admin",
        secret="invalid",
    )

    with pytest.raises(HTTPException) as exc_info:
        issue_credential_from_template(template_id, request, Service())

    assert exc_info.value.status_code == 400
