"""Workflow mermaid CLI integration tests."""

from __future__ import annotations
import httpx
import respx
from orcheo_sdk.cli.main import app
from typer.testing import CliRunner


def test_workflow_mermaid_with_edge_list_format(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test mermaid generation with edges as list tuples."""
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {"nodes": [{"id": "a"}, {"id": "b"}], "edges": [["a", "b"]]},
        }
    ]
    runs: list[dict] = []

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        router.get("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(200, json=runs)
        )
        result = runner.invoke(app, ["workflow", "show", "wf-1"], env=env)
    assert result.exit_code == 0
    assert "a --> b" in result.stdout


def test_workflow_mermaid_with_invalid_edge(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test mermaid generation skips invalid edges."""
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {
                "nodes": [{"id": "a"}],
                "edges": [
                    "invalid",  # String, not a valid edge format
                    {"from": "a"},  # Missing 'to'
                    {"to": "b"},  # Missing 'from'
                ],
            },
        }
    ]
    runs: list[dict] = []

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        router.get("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(200, json=runs)
        )
        result = runner.invoke(app, ["workflow", "show", "wf-1"], env=env)
    assert result.exit_code == 0
