from __future__ import annotations
from uuid import UUID, uuid4
from fastapi import status
from fastapi.testclient import TestClient
from orcheo.models import CredentialHealthStatus
from orcheo.vault import InMemoryCredentialVault


def test_credential_template_crud_and_issuance(api_client: TestClient) -> None:
    create_response = api_client.post(
        "/api/credentials/templates",
        json={
            "name": "GitHub",
            "provider": "github",
            "scopes": ["repo:read"],
            "description": "GitHub token",
            "kind": "secret",
            "actor": "tester",
        },
    )
    assert create_response.status_code == 201
    template = create_response.json()
    template_id = template["id"]

    fetch_response = api_client.get(f"/api/credentials/templates/{template_id}")
    assert fetch_response.status_code == 200

    list_response = api_client.get("/api/credentials/templates")
    assert list_response.status_code == 200
    assert any(item["id"] == template_id for item in list_response.json())

    update_response = api_client.patch(
        f"/api/credentials/templates/{template_id}",
        json={"description": "Rotated", "actor": "tester"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["description"] == "Rotated"

    issue_response = api_client.post(
        f"/api/credentials/templates/{template_id}/issue",
        json={
            "template_id": template_id,
            "secret": "sup3r-secret",
            "actor": "tester",
            "name": "GitHub Prod",
        },
    )
    assert issue_response.status_code == 201
    issued = issue_response.json()
    assert issued["name"] == "GitHub Prod"
    assert issued["template_id"] == template_id

    vault: InMemoryCredentialVault = api_client.app.state.vault
    stored = vault.list_credentials()
    assert any(item.template_id == UUID(template_id) for item in stored)

    delete_response = api_client.delete(f"/api/credentials/templates/{template_id}")
    assert delete_response.status_code == 204

    get_response = api_client.get(f"/api/credentials/templates/{template_id}")
    assert get_response.status_code == 404


def test_list_credentials_endpoint_returns_vault_entries(
    api_client: TestClient,
) -> None:
    create_response = api_client.post(
        "/api/credentials/templates",
        json={
            "name": "Stripe Secret",
            "provider": "stripe",
            "scopes": ["payments:read"],
            "kind": "secret",
            "actor": "tester",
        },
    )
    assert create_response.status_code == 201
    template_id = create_response.json()["id"]

    issue_response = api_client.post(
        f"/api/credentials/templates/{template_id}/issue",
        json={
            "template_id": template_id,
            "secret": "sk_test_orcheo",
            "actor": "tester",
            "name": "Stripe Production",
        },
    )
    assert issue_response.status_code == 201
    issued = issue_response.json()

    list_response = api_client.get("/api/credentials")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert isinstance(payload, list)
    assert payload

    credential = next(item for item in payload if item["id"] == issued["credential_id"])
    assert credential["name"] == issued["name"]
    assert credential["provider"] == issued["provider"]
    assert credential["status"] == CredentialHealthStatus.UNKNOWN.value
    assert credential["access"] in {"private", "shared", "public"}
    assert credential["owner"] == "tester"
    assert credential["secret_preview"]


def test_create_credential(api_client: TestClient) -> None:
    workflow_id = uuid4()
    response = api_client.post(
        "/api/credentials",
        json={
            "name": "Canvas API",
            "provider": "api",
            "secret": "sk_test_canvas",
            "actor": "tester",
            "access": "private",
            "workflow_id": str(workflow_id),
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Canvas API"
    assert payload["provider"] == "api"
    assert payload["owner"] == "tester"
    assert payload["access"] == "private"

    fetch_response = api_client.get(
        "/api/credentials",
        params={"workflow_id": str(workflow_id)},
    )

    assert fetch_response.status_code == 200
    entries = fetch_response.json()
    assert any(entry["id"] == payload["id"] for entry in entries)


def test_create_credential_duplicate_name_returns_409(
    api_client: TestClient,
) -> None:
    workflow_id = uuid4()
    payload = {
        "name": "Canvas API",
        "provider": "api",
        "secret": "sk_test_canvas",
        "actor": "tester",
        "access": "private",
        "workflow_id": str(workflow_id),
    }
    first = api_client.post("/api/credentials", json=payload)
    assert first.status_code == 201

    duplicate = api_client.post("/api/credentials", json=payload)
    assert duplicate.status_code == status.HTTP_409_CONFLICT
    assert "already in use" in duplicate.json()["detail"]


def test_delete_credential(api_client: TestClient) -> None:
    workflow_id = uuid4()
    create_response = api_client.post(
        "/api/credentials",
        json={
            "name": "Canvas API",
            "provider": "api",
            "secret": "sk_test_canvas",
            "actor": "tester",
            "access": "private",
            "workflow_id": str(workflow_id),
        },
    )
    assert create_response.status_code == 201
    credential_id = create_response.json()["id"]

    delete_response = api_client.delete(
        f"/api/credentials/{credential_id}",
        params={"workflow_id": str(workflow_id)},
    )
    assert delete_response.status_code == 204

    fetch_response = api_client.get(
        "/api/credentials",
        params={"workflow_id": str(workflow_id)},
    )
    assert fetch_response.status_code == 200
    payload = fetch_response.json()
    assert all(entry["id"] != credential_id for entry in payload)
