"""Workflow management service helper tests."""

from __future__ import annotations
from typing import Any
import pytest
from orcheo_sdk.services.workflows import management


class DummyClient:
    """Minimal client stub for workflow management service tests."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def delete(self, path: str) -> dict[str, Any] | None:
        self.calls.append({"method": "delete", "path": path})
        return None

    def put(self, path: str, *, json_body: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"method": "put", "path": path, "json_body": json_body})
        return {"ok": True}


def test_delete_workflow_data_falls_back_to_default_message() -> None:
    client = DummyClient()

    result = management.delete_workflow_data(client, "wf-1")

    assert result == {"status": "success", "message": "Workflow 'wf-1' deleted"}
    assert client.calls == [{"method": "delete", "path": "/api/workflows/wf-1"}]


@pytest.mark.parametrize(
    ("kwargs", "expected_payload"),
    [
        ({"name": "Renamed"}, {"actor": "cli", "name": "Renamed"}),
        ({"handle": "renamed-flow"}, {"actor": "cli", "handle": "renamed-flow"}),
        (
            {"description": "Updated description"},
            {"actor": "cli", "description": "Updated description"},
        ),
    ],
)
def test_update_workflow_data_includes_only_provided_fields(
    kwargs: dict[str, Any],
    expected_payload: dict[str, Any],
) -> None:
    client = DummyClient()

    result = management.update_workflow_data(client, "wf-1", **kwargs)

    assert result == {"ok": True}
    assert client.calls == [
        {
            "method": "put",
            "path": "/api/workflows/wf-1",
            "json_body": expected_payload,
        }
    ]
