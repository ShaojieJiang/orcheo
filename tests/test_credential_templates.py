"""Tests for credential template catalog and service."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from orcheo.models import CredentialGovernanceAlert, build_default_template_catalog
from orcheo.vault import InMemoryCredentialVault
from orcheo.vault.templates import CredentialTemplateService
from orcheo_backend.app import create_app


def test_default_catalog_contains_expected_templates() -> None:
    catalog = build_default_template_catalog()
    providers = {template.provider for template in catalog.as_list()}
    assert {"slack", "telegram", "http_basic", "openai_api"}.issubset(providers)


def test_template_issue_validates_inputs() -> None:
    vault = InMemoryCredentialVault()
    catalog = build_default_template_catalog()
    service = CredentialTemplateService(vault, catalog=catalog)

    metadata, alerts = service.issue(
        "http_basic",
        values={"username": "demo", "password": "secret"},
        actor="tester",
    )
    assert metadata.provider == "http_basic"
    assert metadata.health.status.name == "UNKNOWN"
    assert all(isinstance(alert, CredentialGovernanceAlert) for alert in alerts)

    with pytest.raises(ValueError):
        service.issue("http_basic", values={"username": ""}, actor="tester")


def test_backend_exposes_template_endpoints() -> None:
    vault = InMemoryCredentialVault()
    template_service = CredentialTemplateService(vault)
    app = create_app(template_service=template_service)
    client = TestClient(app)

    response = client.get("/api/credentials/templates")
    assert response.status_code == 200
    payload = response.json()
    assert payload["templates"]

    body = {
        "actor": "tester",
        "values": {"bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"},
    }
    response = client.post(
        "/api/credentials/templates/telegram/issue",
        json=body,
    )
    assert response.status_code == 201
    issued = response.json()
    assert issued["credential"]["provider"] == "telegram"
    assert isinstance(issued["alerts"], list)

    bad_response = client.post(
        "/api/credentials/templates/telegram/issue",
        json={"actor": "tester", "values": {"bot_token": "invalid"}},
    )
    assert bad_response.status_code == 422
