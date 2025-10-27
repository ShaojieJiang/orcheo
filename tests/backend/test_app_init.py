"""Additional coverage for backend application helpers."""

from __future__ import annotations
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
        async def list_workflows(self):
            return [workflow1, workflow2]

    result = await list_workflows(Repository())

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
