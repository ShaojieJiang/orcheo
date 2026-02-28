"""Workflow upload CLI tests for LangGraph happy paths."""

from __future__ import annotations
import json
from pathlib import Path
import httpx
import respx
from typer.testing import CliRunner
from orcheo_sdk.cli.main import app


def test_workflow_upload_langgraph_script_create_new(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload creates new workflow from LangGraph script."""
    py_file = tmp_path / "langgraph_workflow.py"
    py_file.write_text(
        """
from langgraph.graph import StateGraph

def greet(state):
    return {"message": "Hello"}

def build_graph():
    graph = StateGraph(dict)
    graph.add_node("greet", greet)
    graph.set_entry_point("greet")
    graph.set_finish_point("greet")
    return graph
""",
        encoding="utf-8",
    )

    created_workflow = {"id": "wf-new", "name": "langgraph-workflow"}
    created_version = {"id": "v-1", "version": 1, "workflow_id": "wf-new"}
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows").mock(
            return_value=httpx.Response(201, json=created_workflow)
        )
        router.post("http://api.test/api/workflows/wf-new/versions/ingest").mock(
            return_value=httpx.Response(201, json=created_version)
        )
        result = runner.invoke(
            app,
            ["workflow", "upload", str(py_file)],
            env=env,
        )
    assert result.exit_code == 0
    assert "Created workflow" in result.stdout
    assert "Ingested LangGraph script as version 1" in result.stdout


def test_workflow_upload_langgraph_script_update_existing(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload adds version to existing workflow from LangGraph."""
    py_file = tmp_path / "langgraph_workflow.py"
    py_file.write_text(
        """
from langgraph.graph import StateGraph

def greet(state):
    return {"message": "Hello Updated"}

def build_graph():
    graph = StateGraph(dict)
    graph.add_node("greet", greet)
    graph.set_entry_point("greet")
    graph.set_finish_point("greet")
    return graph
""",
        encoding="utf-8",
    )

    existing_workflow = {"id": "wf-1", "name": "existing"}
    created_version = {"id": "v-2", "version": 2, "workflow_id": "wf-1"}
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=existing_workflow)
        )
        router.post("http://api.test/api/workflows/wf-1/versions/ingest").mock(
            return_value=httpx.Response(201, json=created_version)
        )
        result = runner.invoke(
            app,
            ["workflow", "upload", str(py_file), "--id", "wf-1"],
            env=env,
        )
    assert result.exit_code == 0
    assert "Ingested LangGraph script as version 2" in result.stdout


def test_workflow_upload_langgraph_script_with_entrypoint(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload with custom entrypoint."""
    py_file = tmp_path / "langgraph_workflow.py"
    py_file.write_text(
        """
from langgraph.graph import StateGraph

def my_custom_graph():
    graph = StateGraph(dict)
    return graph
""",
        encoding="utf-8",
    )

    created_workflow = {"id": "wf-new", "name": "langgraph-workflow"}
    created_version = {"id": "v-1", "version": 1, "workflow_id": "wf-new"}
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows").mock(
            return_value=httpx.Response(201, json=created_workflow)
        )
        ingest_route = router.post(
            "http://api.test/api/workflows/wf-new/versions/ingest"
        ).mock(return_value=httpx.Response(201, json=created_version))
        result = runner.invoke(
            app,
            ["workflow", "upload", str(py_file), "--entrypoint", "my_custom_graph"],
            env=env,
        )
    assert result.exit_code == 0
    # Verify the entrypoint was passed in the request
    request_body = json.loads(ingest_route.calls[0].request.content)
    assert request_body["entrypoint"] == "my_custom_graph"


def test_workflow_upload_langgraph_script_with_runnable_config(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test LangGraph upload forwards runnable config to ingest."""
    py_file = tmp_path / "langgraph_workflow.py"
    py_file.write_text(
        """
from langgraph.graph import StateGraph

def build_graph():
    graph = StateGraph(dict)
    return graph
""",
        encoding="utf-8",
    )
    config_file = tmp_path / "config.json"
    config_file.write_text('{"tags": ["beta"], "recursion_limit": 5}', encoding="utf-8")

    created_workflow = {"id": "wf-new", "name": "langgraph-workflow"}
    created_version = {"id": "v-1", "version": 1, "workflow_id": "wf-new"}
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows").mock(
            return_value=httpx.Response(201, json=created_workflow)
        )
        ingest_route = router.post(
            "http://api.test/api/workflows/wf-new/versions/ingest"
        ).mock(return_value=httpx.Response(201, json=created_version))
        result = runner.invoke(
            app,
            [
                "workflow",
                "upload",
                str(py_file),
                "--config-file",
                str(config_file),
            ],
            env=env,
        )
    assert result.exit_code == 0
    request_body = json.loads(ingest_route.calls[0].request.content)
    assert request_body["runnable_config"]["tags"] == ["beta"]
    assert request_body["runnable_config"]["recursion_limit"] == 5


def test_workflow_upload_langgraph_script_create_new_with_name_override(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test LangGraph upload allows renaming during creation."""
    py_file = tmp_path / "langgraph_workflow.py"
    py_file.write_text(
        """
from langgraph.graph import StateGraph

def build_graph():
    graph = StateGraph(dict)
    return graph
""",
        encoding="utf-8",
    )

    created_workflow = {"id": "wf-new", "name": "custom-workflow"}
    created_version = {"id": "v-1", "version": 1, "workflow_id": "wf-new"}
    with respx.mock(assert_all_called=True) as router:
        create_route = router.post("http://api.test/api/workflows").mock(
            return_value=httpx.Response(201, json=created_workflow)
        )
        router.post("http://api.test/api/workflows/wf-new/versions/ingest").mock(
            return_value=httpx.Response(201, json=created_version)
        )
        result = runner.invoke(
            app,
            [
                "workflow",
                "upload",
                str(py_file),
                "--name",
                "Custom Workflow",
            ],
            env=env,
        )
    assert result.exit_code == 0
    body = json.loads(create_route.calls[0].request.content)
    assert body["name"] == "Custom Workflow"
    assert body["slug"] == "custom-workflow"


def test_workflow_upload_langgraph_script_update_existing_with_name_override(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test LangGraph upload renames existing workflow before ingest."""
    py_file = tmp_path / "langgraph_workflow.py"
    py_file.write_text(
        """
from langgraph.graph import StateGraph

def build_graph():
    graph = StateGraph(dict)
    return graph
""",
        encoding="utf-8",
    )

    existing_workflow = {"id": "wf-1", "name": "Old"}
    created_version = {"id": "v-2", "version": 2, "workflow_id": "wf-1"}
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=existing_workflow)
        )
        rename_route = router.put("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(
                200, json={"id": "wf-1", "name": "Renamed Workflow"}
            )
        )
        ingest_route = router.post(
            "http://api.test/api/workflows/wf-1/versions/ingest"
        ).mock(return_value=httpx.Response(201, json=created_version))
        result = runner.invoke(
            app,
            [
                "workflow",
                "upload",
                str(py_file),
                "--id",
                "wf-1",
                "--name",
                "Renamed Workflow",
            ],
            env=env,
        )
    assert result.exit_code == 0
    rename_body = json.loads(rename_route.calls[0].request.content)
    assert rename_body["name"] == "Renamed Workflow"
    # Ensure ingest still occurs
    assert ingest_route.calls
