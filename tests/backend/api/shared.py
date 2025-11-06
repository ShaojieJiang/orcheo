"""Shared helpers for backend API end-to-end tests."""

from __future__ import annotations
import importlib
from datetime import UTC, datetime, timedelta
from typing import Any
from fastapi.testclient import TestClient
from orcheo.models import CredentialHealthStatus
from orcheo.vault.oauth import (
    OAuthProvider,
    OAuthTokenSecrets,
    OAuthValidationResult,
)


backend_app = importlib.import_module("orcheo_backend.app")


class StaticProvider(OAuthProvider):
    """Simple OAuth provider that returns predetermined validation results."""

    def __init__(
        self,
        *,
        status: CredentialHealthStatus = CredentialHealthStatus.HEALTHY,
        failure_reason: str | None = None,
    ) -> None:
        self.status = status
        self.failure_reason = failure_reason
        self.refresh_calls = 0

    async def refresh_tokens(
        self, metadata: Any, tokens: OAuthTokenSecrets
    ) -> OAuthTokenSecrets:
        """Return refreshed tokens recorded for testing."""

        self.refresh_calls += 1
        return OAuthTokenSecrets(
            access_token="refreshed-token",
            refresh_token="refresh-token",
            expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
        )

    async def validate_tokens(
        self, metadata: Any, tokens: OAuthTokenSecrets
    ) -> OAuthValidationResult:
        """Return the configured validation status."""

        return OAuthValidationResult(
            status=self.status,
            failure_reason=self.failure_reason,
        )


def create_workflow_with_version(api_client: TestClient) -> tuple[str, str]:
    """Create a workflow along with an initial version."""

    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "Webhook Flow", "actor": "tester"},
    )
    workflow_response.raise_for_status()
    workflow_id = workflow_response.json()["id"]

    version_response = api_client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={
            "graph": {"nodes": ["start"], "edges": []},
            "metadata": {},
            "created_by": "tester",
        },
    )
    version_response.raise_for_status()
    version_id = version_response.json()["id"]

    return workflow_id, version_id
