from __future__ import annotations
from fastapi.testclient import TestClient


def test_workflow_crud_operations(api_client: TestClient) -> None:
    """Validate workflow creation, retrieval, update, and archival."""

    create_response = api_client.post(
        "/api/workflows",
        json={
            "name": "Sample Flow",
            "description": "Initial description",
            "tags": ["Demo", "Example"],
            "actor": "tester",
        },
    )
    assert create_response.status_code == 201
    workflow = create_response.json()
    workflow_id = workflow["id"]
    assert workflow["slug"] == "sample-flow"

    get_response = api_client.get(f"/api/workflows/{workflow_id}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Sample Flow"

    update_response = api_client.put(
        f"/api/workflows/{workflow_id}",
        json={"description": "Updated description", "actor": "tester"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["description"] == "Updated description"

    list_response = api_client.get("/api/workflows")
    assert list_response.status_code == 200
    assert any(item["id"] == workflow_id for item in list_response.json())

    delete_response = api_client.delete(
        f"/api/workflows/{workflow_id}",
        params={"actor": "tester"},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["is_archived"] is True


def test_workflow_versions_and_diff(api_client: TestClient) -> None:
    """Ensure version creation, retrieval, and diffing all function."""

    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "Diff Flow", "actor": "author"},
    )
    workflow = workflow_response.json()
    workflow_id = workflow["id"]

    version_one = api_client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={
            "graph": {"nodes": ["start"], "edges": []},
            "metadata": {"notes": "v1"},
            "created_by": "author",
        },
    )
    assert version_one.status_code == 201
    version_two = api_client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={
            "graph": {
                "nodes": ["start", "end"],
                "edges": [{"from": "start", "to": "end"}],
            },
            "metadata": {"notes": "v2"},
            "created_by": "author",
            "notes": "Adds end node",
        },
    )
    assert version_two.status_code == 201

    list_versions = api_client.get(f"/api/workflows/{workflow_id}/versions")
    assert list_versions.status_code == 200
    versions = list_versions.json()
    assert [version["version"] for version in versions] == [1, 2]

    version_detail = api_client.get(f"/api/workflows/{workflow_id}/versions/2")
    assert version_detail.status_code == 200
    assert version_detail.json()["version"] == 2

    diff_response = api_client.get(f"/api/workflows/{workflow_id}/versions/1/diff/2")
    assert diff_response.status_code == 200
    diff_payload = diff_response.json()
    assert diff_payload["base_version"] == 1
    assert diff_payload["target_version"] == 2
    diff_lines = diff_payload["diff"]
    assert any('+    "end"' in line for line in diff_lines)


def test_workflow_handle_lookup_and_update(api_client: TestClient) -> None:
    """Workflow handle should work as a routable ref and support updates."""
    create_response = api_client.post(
        "/api/workflows",
        json={
            "name": "Handle Flow",
            "handle": "handle-flow",
            "actor": "tester",
        },
    )
    assert create_response.status_code == 201
    workflow = create_response.json()
    assert workflow["handle"] == "handle-flow"

    get_response = api_client.get("/api/workflows/handle-flow")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == workflow["id"]

    update_response = api_client.put(
        "/api/workflows/handle-flow",
        json={
            "name": "Renamed Handle Flow",
            "handle": "renamed-handle-flow",
            "actor": "tester",
        },
    )
    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["name"] == "Renamed Handle Flow"
    assert payload["handle"] == "renamed-handle-flow"

    old_handle_response = api_client.get("/api/workflows/handle-flow")
    assert old_handle_response.status_code == 404

    new_handle_response = api_client.get("/api/workflows/renamed-handle-flow")
    assert new_handle_response.status_code == 200
    assert new_handle_response.json()["id"] == workflow["id"]


def test_workflow_create_rejects_uuid_like_handle(api_client: TestClient) -> None:
    """Workflow handles should not accept UUID-shaped values."""

    response = api_client.post(
        "/api/workflows",
        json={
            "name": "UUID Handle",
            "handle": "550e8400-e29b-41d4-a716-446655440000",
            "actor": "tester",
        },
    )

    assert response.status_code == 422
    assert "UUID format" in str(response.json())


def test_openapi_uses_workflow_ref_for_handle_aware_paths(
    api_client: TestClient,
) -> None:
    """Handle-aware routes should document a consistent path parameter name."""

    response = api_client.get("/openapi.json")
    assert response.status_code == 200

    paths = response.json()["paths"]
    expected_paths = [
        "/api/workflows/{workflow_ref}/runs",
        "/api/workflows/{workflow_ref}/executions",
        "/api/workflows/{workflow_ref}/triggers/webhook/config",
        "/api/workflows/{workflow_ref}/triggers/cron/config",
        "/api/workflows/{workflow_ref}/credentials/health",
        "/api/workflows/{workflow_ref}/agentensor/checkpoints",
        "/api/chatkit/workflows/{workflow_ref}/trigger",
    ]

    for path in expected_paths:
        assert path in paths
        operation = next(iter(paths[path].values()))
        assert any(
            parameter["name"] == "workflow_ref"
            for parameter in operation.get("parameters", [])
        )
