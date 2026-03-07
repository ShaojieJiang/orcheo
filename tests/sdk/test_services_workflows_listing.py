"""Workflow listing service tests."""

from __future__ import annotations
from types import SimpleNamespace
from orcheo_sdk.services.workflows import listing


def test_show_workflow_data_fetches_workflow_versions_and_runs(
    monkeypatch,
) -> None:
    """Show helper fetches all payloads and resolves latest version and recent runs."""
    calls: list[str] = []
    workflow = {"id": "wf-1", "name": "Demo"}
    versions = [{"id": "ver-1", "version": 1}, {"id": "ver-2", "version": 2}]
    runs = [
        {"id": f"run-{index}", "created_at": f"2024-01-{index:02d}T00:00:00Z"}
        for index in range(1, 8)
    ]

    def fake_get(path: str) -> object:
        calls.append(path)
        if path == "/api/workflows/wf-1":
            return workflow
        if path == "/api/workflows/wf-1/versions":
            return versions
        return runs

    monkeypatch.setattr(
        listing,
        "enrich_workflow_publish_metadata",
        lambda _client, payload: {**payload, "enriched": True},
    )
    client = SimpleNamespace(get=fake_get)

    result = listing.show_workflow_data(client, "wf-1")

    assert calls == [
        "/api/workflows/wf-1",
        "/api/workflows/wf-1/versions",
        "/api/workflows/wf-1/runs",
    ]
    assert result["workflow"]["enriched"] is True
    assert result["selected_version"] == {"id": "ver-2", "version": 2}
    assert len(result["recent_runs"]) == 5
    assert result["recent_runs"][0]["id"] == "run-7"


def test_show_workflow_data_skips_runs_when_include_runs_disabled(
    monkeypatch,
) -> None:
    """Show helper skips run fetching when include_runs is False."""
    monkeypatch.setattr(
        listing,
        "enrich_workflow_publish_metadata",
        lambda _client, payload: payload,
    )

    def fail_get(_path: str) -> object:
        raise AssertionError("client.get should not be called")

    client = SimpleNamespace(get=fail_get)

    result = listing.show_workflow_data(
        client,
        "wf-1",
        include_runs=False,
        workflow={"id": "wf-1"},
        versions=[],
    )

    assert result["recent_runs"] == []
