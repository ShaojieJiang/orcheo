"""Code generation service tests."""

from __future__ import annotations
from types import SimpleNamespace
from orcheo_sdk.services import codegen


def test_generate_workflow_scaffold_fetches_workflow_and_versions() -> None:
    """Scaffold data fetches workflow metadata and versions when omitted."""
    workflow = {"id": "wf-1", "name": "Demo"}
    versions = [{"id": "ver-2", "version": 2}, {"id": "ver-1", "version": 1}]
    calls: list[str] = []

    def fake_get(path: str) -> object:
        calls.append(path)
        if path == "/api/workflows/wf-1":
            return workflow
        return versions

    client = SimpleNamespace(base_url="http://api.test", get=fake_get)

    result = codegen.generate_workflow_scaffold_data(client, "wf-1")

    assert calls == ["/api/workflows/wf-1", "/api/workflows/wf-1/versions"]
    assert result["workflow"] == workflow
    assert result["versions"] == versions
    assert 'workflow_version_id="ver-2"' in result["code"]
