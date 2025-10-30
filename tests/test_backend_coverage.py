"""Additional tests to achieve 100% coverage for orcheo_backend.app.__init__."""

import asyncio
import importlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from orcheo.models import AesGcmCredentialCipher
from orcheo.vault import InMemoryCredentialVault
from orcheo.vault.oauth import OAuthCredentialService
from orcheo_backend.app import create_app
from orcheo_backend.app.chatkit_store_sqlite import SqliteChatKitStore
from orcheo_backend.app.repository import InMemoryWorkflowRepository


backend_app = importlib.import_module("orcheo_backend.app")


@pytest.fixture()
def api_client() -> TestClient:
    """Yield a configured API client backed by a fresh repository."""
    cipher = AesGcmCredentialCipher(key="test-key")
    vault = InMemoryCredentialVault(cipher=cipher)
    service = OAuthCredentialService(vault, token_ttl_seconds=600, providers={})
    repository = InMemoryWorkflowRepository(credential_service=service)
    app = create_app(repository, credential_service=service)
    app.state.vault = vault
    app.state.credential_service = service
    return TestClient(app)


def test_get_chatkit_store_when_no_server() -> None:
    """Test _get_chatkit_store when server is None."""
    with patch.dict(backend_app._chatkit_server_ref, {"server": None}):
        result = backend_app._get_chatkit_store()
        assert result is None


def test_get_chatkit_store_when_not_sqlite_store() -> None:
    """Test _get_chatkit_store when store is not SqliteChatKitStore."""
    mock_server = Mock()
    mock_server.store = Mock()  # Not a SqliteChatKitStore
    with patch.dict(backend_app._chatkit_server_ref, {"server": mock_server}):
        result = backend_app._get_chatkit_store()
        assert result is None


def test_get_chatkit_store_when_no_store_attr() -> None:
    """Test _get_chatkit_store when server has no store attribute."""
    mock_server = Mock(spec=[])  # No store attribute
    with patch.dict(backend_app._chatkit_server_ref, {"server": mock_server}):
        result = backend_app._get_chatkit_store()
        assert result is None


@pytest.mark.asyncio
async def test_ensure_chatkit_cleanup_task_when_no_store() -> None:
    """Test _ensure_chatkit_cleanup_task when store is None."""
    with patch.dict(backend_app._chatkit_cleanup_task, {"task": None}):
        with patch.object(backend_app, "_get_chatkit_store", return_value=None):
            await backend_app._ensure_chatkit_cleanup_task()
            # Task should remain None since store is None
            assert backend_app._chatkit_cleanup_task["task"] is None


@pytest.mark.asyncio
async def test_cancel_chatkit_cleanup_task_when_no_task() -> None:
    """Test _cancel_chatkit_cleanup_task when task is None."""
    with patch.dict(backend_app._chatkit_cleanup_task, {"task": None}):
        await backend_app._cancel_chatkit_cleanup_task()
        # Should return early without error
        assert backend_app._chatkit_cleanup_task["task"] is None


@pytest.mark.asyncio
async def test_chatkit_cleanup_task_with_valid_store(tmp_path: Any) -> None:
    """Test that cleanup task starts when a valid store is present."""
    # Create a SqliteChatKitStore and mock its prune method
    db_path = tmp_path / "chatkit_test.sqlite"
    store = SqliteChatKitStore(str(db_path))

    # Mock the prune method to return a count

    async def mock_prune(*args: Any, **kwargs: Any) -> int:
        # Return 0 to indicate nothing was pruned
        return 0

    store.prune_threads_older_than = mock_prune  # type: ignore[method-assign]

    # Create a mock server with the real store
    mock_server = Mock()
    mock_server.store = store

    with patch.dict(backend_app._chatkit_server_ref, {"server": mock_server}):
        with patch.dict(backend_app._chatkit_cleanup_task, {"task": None}):
            # Patch the cleanup interval to be very short
            with patch.object(backend_app, "_CHATKIT_CLEANUP_INTERVAL_SECONDS", 0.05):
                # Start the cleanup task
                await backend_app._ensure_chatkit_cleanup_task()
                task = backend_app._chatkit_cleanup_task["task"]
                assert task is not None

                # Wait for at least one cleanup cycle
                await asyncio.sleep(0.15)

                # Cancel the task
                await backend_app._cancel_chatkit_cleanup_task()
                assert backend_app._chatkit_cleanup_task["task"] is None


@pytest.mark.asyncio
async def test_chatkit_gateway_validation_error(api_client: TestClient) -> None:
    """Test chatkit_gateway with invalid payload returns 400."""
    response = api_client.post(
        "/api/chatkit",
        json={"invalid": "payload"},
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Invalid ChatKit payload" in detail["message"]
    assert "errors" in detail


@pytest.mark.asyncio
async def test_chatkit_gateway_streaming_response(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test chatkit_gateway returns streaming response."""
    from chatkit.server import StreamingResult

    async def mock_stream() -> AsyncIterator[bytes]:
        yield b"data: test\n\n"

    mock_result = StreamingResult(mock_stream())

    async def mock_process(payload: bytes, context: Any) -> StreamingResult:
        return mock_result

    mock_server = AsyncMock()
    mock_server.process = mock_process

    # Mock TypeAdapter to bypass validation
    mock_adapter = Mock()
    mock_adapter.validate_json.return_value = {"action": "chat"}

    monkeypatch.setattr(backend_app, "get_chatkit_server", lambda: mock_server)
    monkeypatch.setattr(backend_app, "TypeAdapter", lambda x: mock_adapter)

    response = api_client.post(
        "/api/chatkit",
        json={"test": "payload"},
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_chatkit_gateway_json_response_with_callable(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test chatkit_gateway with callable json payload."""

    class MockResult:
        def __init__(self) -> None:
            self.json = lambda: {"result": "success"}
            self.status_code = 200
            self.headers = {"x-custom": "header"}
            self.media_type = "application/json"

    async def mock_process(payload: bytes, context: Any) -> MockResult:
        return MockResult()

    mock_server = AsyncMock()
    mock_server.process = mock_process

    # Mock TypeAdapter to bypass validation
    mock_adapter = Mock()
    mock_adapter.validate_json.return_value = {"action": "chat"}

    monkeypatch.setattr(backend_app, "get_chatkit_server", lambda: mock_server)
    monkeypatch.setattr(backend_app, "TypeAdapter", lambda x: mock_adapter)

    response = api_client.post("/api/chatkit", json={"test": "payload"})

    assert response.status_code == 200
    assert response.json() == {"result": "success"}


@pytest.mark.asyncio
async def test_chatkit_gateway_json_response_with_bytes(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test chatkit_gateway with bytes payload."""

    class MockResult:
        def __init__(self) -> None:
            self.json = b"binary-data"
            self.status_code = 200
            self.headers = None
            self.media_type = "application/octet-stream"

    async def mock_process(payload: bytes, context: Any) -> MockResult:
        return MockResult()

    mock_server = AsyncMock()
    mock_server.process = mock_process

    # Mock TypeAdapter to bypass validation
    mock_adapter = Mock()
    mock_adapter.validate_json.return_value = {"action": "chat"}

    monkeypatch.setattr(backend_app, "get_chatkit_server", lambda: mock_server)
    monkeypatch.setattr(backend_app, "TypeAdapter", lambda x: mock_adapter)

    response = api_client.post("/api/chatkit", json={"test": "payload"})

    assert response.status_code == 200
    assert response.content == b"binary-data"


@pytest.mark.asyncio
async def test_chatkit_gateway_json_response_with_string(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test chatkit_gateway with string payload."""

    class MockResult:
        def __init__(self) -> None:
            self.json = "text response"
            self.status_code = 200
            self.headers = [("x-custom", "value")]
            self.media_type = "text/plain"

    async def mock_process(payload: bytes, context: Any) -> MockResult:
        return MockResult()

    mock_server = AsyncMock()
    mock_server.process = mock_process

    # Mock TypeAdapter to bypass validation
    mock_adapter = Mock()
    mock_adapter.validate_json.return_value = {"action": "chat"}

    monkeypatch.setattr(backend_app, "get_chatkit_server", lambda: mock_server)
    monkeypatch.setattr(backend_app, "TypeAdapter", lambda x: mock_adapter)

    response = api_client.post("/api/chatkit", json={"test": "payload"})

    assert response.status_code == 200
    assert response.text == "text response"


@pytest.mark.asyncio
async def test_chatkit_gateway_dict_response(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test chatkit_gateway with dict result (no json attribute)."""

    async def mock_process(payload: bytes, context: Any) -> dict[str, str]:
        return {"status": "ok"}

    mock_server = AsyncMock()
    mock_server.process = mock_process

    # Mock TypeAdapter to bypass validation
    mock_adapter = Mock()
    mock_adapter.validate_json.return_value = {"action": "chat"}

    monkeypatch.setattr(backend_app, "get_chatkit_server", lambda: mock_server)
    monkeypatch.setattr(backend_app, "TypeAdapter", lambda x: mock_adapter)

    response = api_client.post("/api/chatkit", json={"test": "payload"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_app_startup_exception_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that startup handler gracefully handles HTTPException."""

    def mock_get_chatkit_server() -> None:
        raise HTTPException(status_code=503, detail="ChatKit not configured")

    monkeypatch.setattr(backend_app, "get_chatkit_server", mock_get_chatkit_server)

    cipher = AesGcmCredentialCipher(key="test-key")
    vault = InMemoryCredentialVault(cipher=cipher)
    service = OAuthCredentialService(vault, token_ttl_seconds=600, providers={})
    repository = InMemoryWorkflowRepository(credential_service=service)

    # Create app - this should not raise despite get_chatkit_server failing
    app = create_app(repository, credential_service=service)

    # Test that startup event handler catches the HTTPException
    with TestClient(app) as client:
        # Just creating the client triggers startup events
        # The test passes if no exception is raised
        assert client is not None


@pytest.mark.asyncio
async def test_credential_health_get_without_service(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test credential health endpoint when service is None."""
    # Create workflow
    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "Test Flow", "actor": "tester"},
    )
    workflow_id = workflow_response.json()["id"]

    # Override credential service to None
    monkeypatch.setitem(backend_app._credential_service_ref, "service", None)
    api_client.app.dependency_overrides[backend_app.get_credential_service] = (
        lambda: None
    )

    response = api_client.get(f"/api/workflows/{workflow_id}/credentials/health")
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


@pytest.mark.asyncio
async def test_credential_health_validate_without_service(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test credential validation endpoint when service is None."""
    # Create workflow
    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "Test Flow", "actor": "tester"},
    )
    workflow_id = workflow_response.json()["id"]

    # Override credential service to None
    monkeypatch.setitem(backend_app._credential_service_ref, "service", None)
    api_client.app.dependency_overrides[backend_app.get_credential_service] = (
        lambda: None
    )

    response = api_client.post(
        f"/api/workflows/{workflow_id}/credentials/validate",
        json={"actor": "tester"},
    )
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_delete_credential_not_found(api_client: TestClient) -> None:
    """Test deleting a non-existent credential returns 404."""
    missing_id = uuid4()
    response = api_client.delete(f"/api/credentials/{missing_id}")
    assert response.status_code == 404


def test_delete_credential_scope_violation(api_client: TestClient) -> None:
    """Test deleting a credential with wrong workflow context returns 403."""
    workflow_id = uuid4()
    other_workflow_id = uuid4()

    # Create a credential scoped to workflow_id
    create_response = api_client.post(
        "/api/credentials",
        json={
            "name": "Scoped Cred",
            "provider": "test",
            "secret": "secret",
            "actor": "tester",
            "access": "private",
            "workflow_id": str(workflow_id),
        },
    )
    credential_id = create_response.json()["id"]

    # Try to delete with wrong workflow context
    response = api_client.delete(
        f"/api/credentials/{credential_id}",
        params={"workflow_id": str(other_workflow_id)},
    )
    assert response.status_code == 403


def test_create_credential_with_value_error(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test creating credential that raises ValueError returns 422."""
    vault = api_client.app.state.vault

    def mock_create_credential(*args: Any, **kwargs: Any) -> None:
        raise ValueError("Invalid credential configuration")

    monkeypatch.setattr(vault, "create_credential", mock_create_credential)

    response = api_client.post(
        "/api/credentials",
        json={
            "name": "Test Cred",
            "provider": "test",
            "secret": "secret",
            "actor": "tester",
            "access": "public",
            "kind": "secret",
        },
    )
    assert response.status_code == 422


def test_list_workflows_includes_archived(api_client: TestClient) -> None:
    """Test list workflows with include_archived=True."""
    # Create and archive a workflow
    create_response = api_client.post(
        "/api/workflows",
        json={"name": "To Archive", "actor": "tester"},
    )
    workflow_id = create_response.json()["id"]

    api_client.delete(f"/api/workflows/{workflow_id}", params={"actor": "tester"})

    # List without archived
    response = api_client.get("/api/workflows")
    assert workflow_id not in [w["id"] for w in response.json()]

    # List with archived
    response = api_client.get("/api/workflows?include_archived=true")
    assert any(w["id"] == workflow_id for w in response.json())


def test_ingest_workflow_version_script_error(api_client: TestClient) -> None:
    """Test ingesting invalid script returns 400."""
    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "Bad Script", "actor": "tester"},
    )
    workflow_id = workflow_response.json()["id"]

    response = api_client.post(
        f"/api/workflows/{workflow_id}/versions/ingest",
        json={
            "script": "invalid python code!!!",
            "entrypoint": "app",
            "created_by": "tester",
        },
    )
    assert response.status_code == 400


def test_webhook_trigger_credential_health_error(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test webhook trigger surfaces credential health errors."""
    from orcheo.vault.oauth import CredentialHealthError, CredentialHealthReport

    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "Webhook Flow", "actor": "tester"},
    )
    workflow_id = workflow_response.json()["id"]

    api_client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={"graph": {}, "metadata": {}, "created_by": "tester"},
    )

    # Mock repository to raise CredentialHealthError
    repository = api_client.app.dependency_overrides[backend_app.get_repository]()

    async def failing_webhook_handler(*args: Any, **kwargs: Any) -> None:
        report = CredentialHealthReport(
            workflow_id=uuid4(), results=[], checked_at=datetime.now(tz=UTC)
        )
        raise CredentialHealthError(report)

    monkeypatch.setattr(repository, "handle_webhook_trigger", failing_webhook_handler)

    response = api_client.post(f"/api/workflows/{workflow_id}/triggers/webhook")
    assert response.status_code == 422


def test_dispatch_cron_credential_health_error(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test cron dispatch surfaces credential health errors."""
    from orcheo.vault.oauth import CredentialHealthError, CredentialHealthReport

    repository = api_client.app.dependency_overrides[backend_app.get_repository]()

    async def failing_cron_dispatch(*args: Any, **kwargs: Any) -> None:
        report = CredentialHealthReport(
            workflow_id=uuid4(), results=[], checked_at=datetime.now(tz=UTC)
        )
        raise CredentialHealthError(report)

    monkeypatch.setattr(repository, "dispatch_due_cron_runs", failing_cron_dispatch)

    response = api_client.post("/api/triggers/cron/dispatch")
    assert response.status_code == 422


def test_dispatch_manual_credential_health_error(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test manual dispatch surfaces credential health errors."""
    from orcheo.vault.oauth import CredentialHealthError, CredentialHealthReport

    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "Manual Flow", "actor": "tester"},
    )
    workflow_id = workflow_response.json()["id"]

    repository = api_client.app.dependency_overrides[backend_app.get_repository]()

    async def failing_manual_dispatch(*args: Any, **kwargs: Any) -> None:
        report = CredentialHealthReport(
            workflow_id=uuid4(), results=[], checked_at=datetime.now(tz=UTC)
        )
        raise CredentialHealthError(report)

    monkeypatch.setattr(repository, "dispatch_manual_runs", failing_manual_dispatch)

    response = api_client.post(
        "/api/triggers/manual/dispatch",
        json={
            "workflow_id": workflow_id,
            "actor": "tester",
            "runs": [{}],
        },
    )
    assert response.status_code == 422
