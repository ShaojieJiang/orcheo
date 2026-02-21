"""Tests for the /api/system/info endpoint."""

from __future__ import annotations
import pytest
from orcheo_backend.app import versioning
from tests.backend.authentication_test_utils import create_test_client, reset_auth_state


@pytest.fixture(autouse=True)
def _reset_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable auth and reset global state between tests."""

    yield from reset_auth_state(monkeypatch)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Reset versioning cache between tests."""

    versioning._cache_state["entry"] = None  # type: ignore[attr-defined]


def test_system_info_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Endpoint returns a successful payload with version data."""

    monkeypatch.setenv("ORCHEO_AUTH_MODE", "disabled")

    monkeypatch.setattr(
        versioning,
        "_read_current_version",
        lambda package: {
            "orcheo-backend": "0.1.0",
            "orcheo-sdk": "0.2.0",
            "orcheo-canvas": "0.3.0",
        }.get(package),
    )
    monkeypatch.setattr(
        versioning, "_fetch_pypi_latest", lambda *args, **kwargs: "0.5.0"
    )
    monkeypatch.setattr(
        versioning, "_fetch_npm_latest", lambda *args, **kwargs: "0.4.0"
    )

    client = create_test_client()
    response = client.get("/api/system/info")

    assert response.status_code == 200
    payload = response.json()
    assert payload["backend"]["current_version"] == "0.1.0"
    assert payload["backend"]["latest_version"] == "0.5.0"
    assert payload["backend"]["update_available"] is True
    assert payload["cli"]["latest_version"] == "0.5.0"
    assert payload["canvas"]["latest_version"] == "0.4.0"
    assert "checked_at" in payload


def test_system_info_registry_failure_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Endpoint soft-fails registry lookup and returns null latest versions."""

    monkeypatch.setenv("ORCHEO_AUTH_MODE", "disabled")

    monkeypatch.setattr(
        versioning,
        "_read_current_version",
        lambda package: {
            "orcheo-backend": "0.1.0",
            "orcheo-sdk": "0.2.0",
            "orcheo-canvas": "0.3.0",
        }.get(package),
    )
    monkeypatch.setattr(versioning, "_fetch_pypi_latest", lambda *args, **kwargs: None)
    monkeypatch.setattr(versioning, "_fetch_npm_latest", lambda *args, **kwargs: None)

    client = create_test_client()
    response = client.get("/api/system/info")

    assert response.status_code == 200
    payload = response.json()
    assert payload["backend"]["latest_version"] is None
    assert payload["backend"]["update_available"] is False
    assert payload["cli"]["latest_version"] is None
    assert payload["canvas"]["latest_version"] is None


def test_system_info_reads_canvas_current_version_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ORCHEO_AUTH_MODE", "disabled")
    monkeypatch.setenv("ORCHEO_CANVAS_VERSION", "1.2.3")

    monkeypatch.setattr(
        versioning,
        "_read_current_version",
        lambda package: {
            "orcheo-backend": "0.1.0",
            "orcheo-sdk": "0.2.0",
        }.get(package),
    )
    monkeypatch.setattr(versioning, "_fetch_pypi_latest", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        versioning, "_fetch_npm_latest", lambda *args, **kwargs: "1.2.4"
    )

    client = create_test_client()
    response = client.get("/api/system/info")

    assert response.status_code == 200
    payload = response.json()
    assert payload["canvas"]["current_version"] == "1.2.3"
    assert payload["canvas"]["latest_version"] == "1.2.4"
    assert payload["canvas"]["update_available"] is True


def test_system_health_is_public_when_auth_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Health endpoint remains available without auth tokens."""
    monkeypatch.setenv("ORCHEO_AUTH_MODE", "required")

    client = create_test_client()
    health_response = client.get("/api/system/health")
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}
