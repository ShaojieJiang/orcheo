from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from orcheo.nodes.registry import NodeMetadata, NodeRegistry
from typer.testing import CliRunner

from orcheo_sdk.cli import app


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def client_stub(monkeypatch):
    responses: dict[tuple[str, str], tuple[int, object]] = {}
    clients: list["DummyClient"] = []

    class DummyClient:
        def __init__(
            self, *, base_url: str, timeout: float | None = None, headers=None
        ):
            self.base_url = base_url.rstrip("/")
            self.headers = headers or {}
            self.timeout = timeout
            self.requests: list[
                tuple[str, str, dict[str, object] | None, object | None]
            ] = []
            clients.append(self)

        def request(self, method: str, url: str, params=None, json=None):
            if not url.startswith("http"):
                full_url = f"{self.base_url}{url}"
            else:
                full_url = url
            key = (method.upper(), full_url)
            self.requests.append((method.upper(), full_url, params, json))
            if key not in responses:
                request = httpx.Request(method, full_url)
                raise httpx.RequestError("No response registered", request=request)
            status, payload = responses[key]
            request = httpx.Request(method, full_url)
            return httpx.Response(status, request=request, json=payload)

        def close(self) -> None:  # pragma: no cover - simple stub
            return None

    monkeypatch.setattr("orcheo_sdk.cli.api.httpx.Client", DummyClient)
    return responses, clients


def _api_url(base: str) -> str:
    return f"{base.rstrip('/')}/api"


def test_node_list_and_cache(
    runner: CliRunner,
    client_stub,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses, clients = client_stub
    base = "https://api.orcheo.test"
    registry = NodeRegistry()
    registry.register(
        NodeMetadata(
            name="http_request",
            description="Perform an HTTP request",
            category="data",
        )
    )(lambda _: None)

    monkeypatch.setattr("orcheo_sdk.cli.nodes._get_node_registry", lambda: registry)

    result = runner.invoke(
        app,
        [
            "--api-url",
            base,
            "--cache-dir",
            str(tmp_path),
            "node",
            "list",
        ],
    )
    assert result.exit_code == 0
    assert "http_request" in result.output
    assert responses == {}
    assert clients and not clients[0].requests

    offline_result = runner.invoke(
        app,
        [
            "--api-url",
            base,
            "--cache-dir",
            str(tmp_path),
            "--offline",
            "node",
            "list",
        ],
    )
    assert offline_result.exit_code == 0
    assert "http_request" in offline_result.output
    assert "Served from cache" not in offline_result.output


def test_workflow_show_and_run(runner: CliRunner, client_stub, tmp_path: Path) -> None:
    responses, _ = client_stub
    base = "https://api.orcheo.test"
    workflow_id = "11111111-1111-1111-1111-111111111111"
    responses[("GET", f"{_api_url(base)}/workflows")] = (200, [])
    responses[("GET", f"{_api_url(base)}/workflows/{workflow_id}")] = (
        200,
        {
            "id": workflow_id,
            "name": "Demo",
            "slug": "demo",
            "description": "Demo workflow",
            "tags": ["demo"],
            "updated_at": "2025-01-01T00:00:00+00:00",
        },
    )
    responses[("GET", f"{_api_url(base)}/workflows/{workflow_id}/versions")] = (
        200,
        [
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "version": 1,
                "created_at": "2025-01-01T00:00:00+00:00",
                "created_by": "cli",
                "graph": {
                    "nodes": [
                        {"name": "start", "type": "trigger"},
                        {"name": "task", "type": "action"},
                    ],
                    "edges": [["START", "start"], ["start", "task"], ["task", "END"]],
                },
            }
        ],
    )
    responses[("GET", f"{_api_url(base)}/workflows/{workflow_id}/runs")] = (
        200,
        [
            {
                "id": "33333333-3333-3333-3333-333333333333",
                "status": "succeeded",
                "created_at": "2025-01-02T00:00:00+00:00",
                "completed_at": "2025-01-02T00:01:00+00:00",
            }
        ],
    )
    responses[("POST", f"{_api_url(base)}/workflows/{workflow_id}/runs")] = (
        201,
        {
            "id": "44444444-4444-4444-4444-444444444444",
            "status": "pending",
            "triggered_by": "cli",
            "created_at": "2025-01-03T00:00:00+00:00",
        },
    )

    show_result = runner.invoke(
        app,
        [
            "--api-url",
            base,
            "--cache-dir",
            str(tmp_path),
            "workflow",
            "show",
            workflow_id,
        ],
    )
    assert show_result.exit_code == 0
    assert "flowchart TD" in show_result.output

    run_result = runner.invoke(
        app,
        [
            "--api-url",
            base,
            "--cache-dir",
            str(tmp_path),
            "workflow",
            "run",
            workflow_id,
        ],
    )
    assert run_result.exit_code == 0
    assert "Run ID" in run_result.output


def test_credential_reference_and_create(
    runner: CliRunner, client_stub, tmp_path: Path
) -> None:
    responses, _ = client_stub
    base = "https://api.orcheo.test"
    credentials_payload = [
        {
            "id": "cred-1",
            "name": "demo_credential",
            "provider": "http",
            "access": "private",
            "status": "healthy",
        }
    ]
    responses[("GET", f"{_api_url(base)}/credentials")] = (200, credentials_payload)
    responses[("POST", f"{_api_url(base)}/credentials")] = (
        201,
        {
            "id": "cred-2",
            "name": "new_credential",
            "provider": "slack",
            "access": "shared",
        },
    )
    responses[("DELETE", f"{_api_url(base)}/credentials/cred-1")] = (204, None)

    reference_result = runner.invoke(
        app,
        [
            "--api-url",
            base,
            "--cache-dir",
            str(tmp_path),
            "credential",
            "reference",
            "demo_credential",
        ],
    )
    assert reference_result.exit_code == 0
    assert "[[demo_credential]]" in reference_result.output

    create_result = runner.invoke(
        app,
        [
            "--api-url",
            base,
            "--cache-dir",
            str(tmp_path),
            "credential",
            "create",
            "--name",
            "new_credential",
            "--provider",
            "slack",
            "--secret",
            "secret",
            "--access",
            "shared",
            "--scopes",
            "chat:write",
        ],
    )
    assert create_result.exit_code == 0
    assert "Credential Created" in create_result.output

    delete_result = runner.invoke(
        app,
        [
            "--api-url",
            base,
            "--cache-dir",
            str(tmp_path),
            "credential",
            "delete",
            "cred-1",
        ],
    )
    assert delete_result.exit_code == 0
    assert "deleted successfully" in delete_result.output


def test_node_show_displays_details(
    runner: CliRunner, client_stub, tmp_path: Path
) -> None:
    responses, _ = client_stub
    base = "https://api.orcheo.test"
    responses[("GET", f"{_api_url(base)}/nodes/catalog/example")] = (
        200,
        {
            "name": "example",
            "type": "utility",
            "version": "1.2.3",
            "category": "utility",
            "description": "Example node",
            "inputs": [
                {
                    "name": "query",
                    "type": "string",
                    "required": True,
                    "description": "Search query",
                }
            ],
            "outputs": [
                {
                    "name": "results",
                    "type": "list",
                    "required": False,
                    "description": "Result set",
                }
            ],
            "credentials": [{"name": "search_api", "description": "Search API key"}],
        },
    )

    result = runner.invoke(
        app,
        [
            "--api-url",
            base,
            "--cache-dir",
            str(tmp_path),
            "node",
            "show",
            "example",
        ],
    )
    assert result.exit_code == 0
    assert "Search API key" in result.output
    assert "Inputs" in result.output
    assert "Outputs" in result.output


def test_workflow_list_and_invalid_inputs(
    runner: CliRunner, client_stub, tmp_path: Path
) -> None:
    responses, _ = client_stub
    base = "https://api.orcheo.test"
    responses[("GET", f"{_api_url(base)}/workflows")] = (
        200,
        [
            {
                "id": "wf-1",
                "name": "Workflow One",
                "slug": "workflow-one",
                "updated_at": "2025-02-02T00:00:00+00:00",
            }
        ],
    )

    list_result = runner.invoke(
        app,
        [
            "--api-url",
            base,
            "--cache-dir",
            str(tmp_path),
            "workflow",
            "list",
        ],
    )
    assert list_result.exit_code == 0
    assert "Workflow One" in list_result.output

    invalid_result = runner.invoke(
        app,
        [
            "--api-url",
            base,
            "--cache-dir",
            str(tmp_path),
            "workflow",
            "run",
            "wf-1",
            "--inputs",
            "[]",
        ],
    )
    assert invalid_result.exit_code == 1
    assert "Inputs must be a JSON object" in invalid_result.output


def test_credential_list_command(
    runner: CliRunner, client_stub, tmp_path: Path
) -> None:
    responses, _ = client_stub
    base = "https://api.orcheo.test"
    responses[("GET", f"{_api_url(base)}/credentials")] = (
        200,
        [
            {
                "id": "cred-1",
                "name": "first",
                "provider": "http",
                "access": "shared",
                "status": "healthy",
            }
        ],
    )

    result = runner.invoke(
        app,
        [
            "--api-url",
            base,
            "--cache-dir",
            str(tmp_path),
            "credential",
            "list",
        ],
    )
    assert result.exit_code == 0
    assert "first" in result.output


def test_code_scaffold(runner: CliRunner, client_stub, tmp_path: Path) -> None:
    responses, _ = client_stub
    base = "https://api.orcheo.test"
    workflow_id = "55555555-5555-5555-5555-555555555555"
    responses[("GET", f"{_api_url(base)}/workflows/{workflow_id}/versions")] = (
        200,
        [
            {
                "id": "66666666-6666-6666-6666-666666666666",
                "version": 2,
                "created_at": "2025-01-01T00:00:00+00:00",
                "created_by": "cli",
            }
        ],
    )

    result = runner.invoke(
        app,
        [
            "--api-url",
            base,
            "--cache-dir",
            str(tmp_path),
            "code",
            "scaffold",
            workflow_id,
        ],
    )
    assert result.exit_code == 0
    assert "HttpWorkflowExecutor" in result.output


def test_profile_configuration_precedence(
    runner: CliRunner,
    client_stub,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses, clients = client_stub
    config_path = tmp_path / "cli.toml"
    config_path.write_text(
        """
[profiles.dev]
api_url = "https://profile.orcheo.test"
service_token = "profile-token"
        """.strip()
    )
    base = "https://profile.orcheo.test"
    registry = NodeRegistry()
    registry.register(
        NodeMetadata(
            name="storage",
            description="Persist data to storage",
            category="storage",
        )
    )(lambda _: None)

    monkeypatch.setattr("orcheo_sdk.cli.nodes._get_node_registry", lambda: registry)

    result = runner.invoke(
        app,
        [
            "--profile",
            "dev",
            "--config-path",
            str(config_path),
            "--cache-dir",
            str(tmp_path),
            "node",
            "list",
        ],
    )
    assert result.exit_code == 0
    assert "storage" in result.output
    assert clients and not clients[0].requests
    assert clients, "No HTTP client was created"
    assert clients[0].headers.get("Authorization") == "Bearer profile-token"
