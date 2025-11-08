from __future__ import annotations
from typing import Any
from orcheo_sdk.services.workflows import publish as publish_module


class DummyClient:
    """Minimal client stub for publish service tests."""

    def __init__(self, *, base_url: str, response: Any) -> None:
        self.base_url = base_url
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def post(self, path: str, *, json_body: dict[str, Any]) -> Any:
        self.calls.append({"path": path, "json_body": json_body})
        return self.response


def test_build_share_url_strips_api_segment() -> None:
    url = publish_module._build_share_url("http://host/api", "wf-123")
    assert url == "http://host/chat/wf-123"
    url_with_slash = publish_module._build_share_url("http://host/api/", "wf-456")
    assert url_with_slash == "http://host/chat/wf-456"


def test_enrich_workflow_preserves_share_url_when_public() -> None:
    workflow = {"id": "wf-1", "is_public": True}
    enriched = publish_module._enrich_workflow("http://api.example.com/api", workflow)
    assert enriched["share_url"] == "http://api.example.com/chat/wf-1"


def test_enrich_workflow_hides_share_url_when_private() -> None:
    workflow = {"id": "wf-1", "is_public": False}
    enriched = publish_module._enrich_workflow("http://api.example.com/api", workflow)
    assert enriched["share_url"] is None


def test_publish_workflow_data_returns_enriched_payload() -> None:
    payload = {
        "workflow": {"id": "wf-1", "is_public": True, "require_login": True},
        "publish_token": "publish-token",
        "message": "Published",
    }
    client = DummyClient(base_url="http://api.example.com/api", response=payload)

    result = publish_module.publish_workflow_data(
        client,
        "wf-1",
        require_login=True,
        actor="cli",
    )

    assert result["share_url"] == "http://api.example.com/chat/wf-1"
    assert result["publish_token"] == "publish-token"
    assert result["message"] == "Published"
    assert client.calls == [
        {
            "path": "/api/workflows/wf-1/publish",
            "json_body": {"require_login": True, "actor": "cli"},
        }
    ]


def test_rotate_publish_token_data_rotates_and_enriches() -> None:
    payload = {
        "workflow": {"id": "wf-2", "is_public": True},
        "publish_token": "rotated",
        "message": "Token rotated",
    }
    client = DummyClient(base_url="http://api.test/api/v1", response=payload)

    result = publish_module.rotate_publish_token_data(
        client,
        "wf-2",
        actor="cli",
    )

    assert result["publish_token"] == "rotated"
    assert result["message"] == "Token rotated"
    assert result["share_url"] == "http://api.test/chat/wf-2"
    assert client.calls == [
        {
            "path": "/api/workflows/wf-2/publish/rotate",
            "json_body": {"actor": "cli"},
        }
    ]


def test_unpublish_workflow_returns_enriched_workflow() -> None:
    workflow = {"id": "wf-3", "is_public": False}
    client = DummyClient(base_url="http://api.test", response=workflow)

    result = publish_module.unpublish_workflow_data(client, "wf-3", actor="cli")

    assert result["workflow"]["share_url"] is None
    assert result["share_url"] is None
    assert client.calls == [
        {
            "path": "/api/workflows/wf-3/publish/revoke",
            "json_body": {"actor": "cli"},
        }
    ]


def test_enrich_workflow_publish_metadata_derives_share_url() -> None:
    workflow = {"id": "wf-4", "is_public": True}
    enriched = publish_module.enrich_workflow_publish_metadata(
        DummyClient(base_url="http://api.test/api", response={}),
        workflow,
    )

    assert enriched["share_url"] == "http://api.test/chat/wf-4"
