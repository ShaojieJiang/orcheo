"""Workflow upload validation and formatting tests."""

from __future__ import annotations
import json
from pathlib import Path
import httpx
import respx
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.main import app
from typer.testing import CliRunner


def test_load_workflow_from_python_missing_workflow_variable(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test loading Python file without 'workflow' treats it as LangGraph script."""
    py_file = tmp_path / "no_workflow.py"
    py_file.write_text("some_other_var = 123", encoding="utf-8")

    # Now it treats files without 'workflow' as LangGraph scripts
    # and tries to create a workflow and ingest them
    created_workflow = {"id": "wf-new", "name": "no-workflow"}
    # The ingestion will fail because it's not valid LangGraph code
    with respx.mock() as router:
        router.post("http://api.test/api/workflows").mock(
            return_value=httpx.Response(201, json=created_workflow)
        )
        router.post("http://api.test/api/workflows/wf-new/versions/ingest").mock(
            return_value=httpx.Response(
                400, json={"detail": "Script did not produce a LangGraph StateGraph"}
            )
        )
        result = runner.invoke(
            app,
            ["workflow", "upload", str(py_file)],
            env=env,
        )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "Failed to ingest LangGraph script" in str(result.exception)


def test_load_workflow_from_python_wrong_type(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test loading Python file with wrong workflow type fails."""
    py_file = tmp_path / "wrong_type.py"
    py_file.write_text("workflow = 'not a Workflow instance'", encoding="utf-8")

    result = runner.invoke(
        app,
        ["workflow", "upload", str(py_file)],
        env=env,
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "must be an orcheo_sdk.Workflow instance" in str(result.exception)


def test_load_workflow_from_json_not_object(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test loading JSON file that is not an object fails."""
    json_file = tmp_path / "array.json"
    json_file.write_text('["not", "an", "object"]', encoding="utf-8")

    result = runner.invoke(
        app,
        ["workflow", "upload", str(json_file)],
        env=env,
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "must contain a JSON object" in str(result.exception)


def test_load_workflow_from_json_missing_name(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test loading JSON file without 'name' field fails."""
    json_file = tmp_path / "no_name.json"
    json_file.write_text('{"graph": {}}', encoding="utf-8")

    result = runner.invoke(
        app,
        ["workflow", "upload", str(json_file)],
        env=env,
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "must include a 'name' field" in str(result.exception)


def test_load_workflow_from_json_missing_graph(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test loading JSON file without 'graph' field fails."""
    json_file = tmp_path / "no_graph.json"
    json_file.write_text('{"name": "Test"}', encoding="utf-8")

    result = runner.invoke(
        app,
        ["workflow", "upload", str(json_file)],
        env=env,
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "must include a 'graph' field" in str(result.exception)


def test_format_workflow_as_json_without_metadata(tmp_path: Path) -> None:
    """Test formatting workflow as JSON without metadata."""
    from orcheo_sdk.cli.workflow import _format_workflow_as_json

    workflow = {"id": "wf-1", "name": "Test"}
    graph = {"nodes": [{"id": "a"}], "edges": []}

    result = _format_workflow_as_json(workflow, graph)
    data = json.loads(result)

    assert data["name"] == "Test"
    assert data["graph"] == graph
    assert "metadata" not in data


def test_format_workflow_as_json_with_metadata(tmp_path: Path) -> None:
    """Test formatting workflow as JSON with metadata."""
    from orcheo_sdk.cli.workflow import _format_workflow_as_json

    workflow = {"id": "wf-1", "name": "Test", "metadata": {"key": "value"}}
    graph = {"nodes": [{"id": "a"}], "edges": []}

    result = _format_workflow_as_json(workflow, graph)
    data = json.loads(result)

    assert data["name"] == "Test"
    assert data["graph"] == graph
    assert data["metadata"] == {"key": "value"}


def test_format_workflow_as_python_multiple_node_types(tmp_path: Path) -> None:
    """Test formatting workflow as Python with multiple node types."""
    from orcheo_sdk.cli.workflow import _format_workflow_as_python

    workflow = {"name": "TestWorkflow"}
    graph = {
        "nodes": [
            {"name": "agent1", "type": "Agent"},
            {"name": "agent2", "type": "Agent"},
            {"name": "code1", "type": "Code"},
        ],
        "edges": [],
    }

    result = _format_workflow_as_python(workflow, graph)

    assert 'workflow = Workflow(name="TestWorkflow")' in result
    assert "class AgentConfig(BaseModel):" in result
    assert "class AgentNode(WorkflowNode[AgentConfig]):" in result
    assert "class CodeConfig(BaseModel):" in result
    assert "class CodeNode(WorkflowNode[CodeConfig]):" in result
    # Should not duplicate Agent classes
    assert result.count("class AgentConfig") == 1
    assert "# TODO: Configure node dependencies" in result


def test_format_workflow_as_python_empty_nodes(tmp_path: Path) -> None:
    """Test formatting workflow as Python with no nodes."""
    from orcheo_sdk.cli.workflow import _format_workflow_as_python

    workflow = {"name": "EmptyWorkflow"}
    graph = {"nodes": [], "edges": []}

    result = _format_workflow_as_python(workflow, graph)

    assert 'workflow = Workflow(name="EmptyWorkflow")' in result
    assert "from orcheo_sdk import Workflow" in result
