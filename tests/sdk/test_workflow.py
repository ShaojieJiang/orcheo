"""Tests for the workflow authoring helpers."""

from __future__ import annotations
import pytest
from orcheo_sdk import (
    OrcheoClient,
    Workflow,
    WorkflowNode,
)
from pydantic import BaseModel


class UppercaseConfig(BaseModel):
    prefix: str


class UppercaseNode(WorkflowNode[UppercaseConfig]):
    type_name = "Uppercase"


class AppendConfig(BaseModel):
    suffix: str


class AppendNode(WorkflowNode[AppendConfig]):
    type_name = "Append"


def test_workflow_requires_unique_node_names() -> None:
    workflow = Workflow(name="demo")
    workflow.add_node(UppercaseNode("upper", UppercaseConfig(prefix="")))
    with pytest.raises(ValueError):
        workflow.add_node(UppercaseNode("upper", UppercaseConfig(prefix="")))


def test_workflow_requires_existing_dependencies() -> None:
    workflow = Workflow(name="demo")
    with pytest.raises(ValueError):
        workflow.add_node(
            AppendNode("append", AppendConfig(suffix="")), depends_on=["missing"]
        )


def test_to_graph_config_matches_langgraph_shape() -> None:
    workflow = Workflow(name="demo")
    workflow.add_node(UppercaseNode("upper", UppercaseConfig(prefix="")))
    workflow.add_node(
        AppendNode("final", AppendConfig(suffix="")), depends_on=["upper"]
    )

    graph = workflow.to_graph_config()
    assert graph["nodes"] == [
        {"name": "upper", "type": "Uppercase", "prefix": ""},
        {"name": "final", "type": "Append", "suffix": ""},
    ]
    assert graph["edges"] == [
        ("START", "upper"),
        ("final", "END"),
        ("upper", "final"),
    ]


def test_deployment_payload_merges_metadata() -> None:
    workflow = Workflow(name="demo", metadata={"team": "platform"})
    workflow.add_node(UppercaseNode("upper", UppercaseConfig(prefix="")))

    payload = workflow.to_deployment_payload(metadata={"owner": "alice"})
    assert payload["name"] == "demo"
    assert payload["metadata"] == {"team": "platform", "owner": "alice"}


def test_client_builds_deployment_requests() -> None:
    workflow = Workflow(name="demo")
    workflow.add_node(UppercaseNode("upper", UppercaseConfig(prefix="")))

    client = OrcheoClient(base_url="http://localhost:8000")
    request = client.build_deployment_request(
        workflow, metadata={"team": "platform"}, headers={"X-Test": "1"}
    )

    assert request.method == "POST"
    assert request.url == "http://localhost:8000/api/workflows"
    assert request.headers == {"X-Test": "1"}
    assert request.json["graph"]["nodes"][0]["name"] == "upper"
    assert request.json["metadata"] == {"team": "platform"}


def test_client_builds_update_requests() -> None:
    workflow = Workflow(name="demo")
    workflow.add_node(UppercaseNode("upper", UppercaseConfig(prefix="")))

    client = OrcheoClient(base_url="https://example.com")
    request = client.build_deployment_request(workflow, workflow_id="wf-123")

    assert request.method == "PUT"
    assert request.url == "https://example.com/api/workflows/wf-123"


def test_node_requires_pydantic_config() -> None:
    class BadNode(WorkflowNode[str]):
        type_name = "Bad"

    with pytest.raises(TypeError):
        BadNode("bad", "not-model")  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        UppercaseNode("upper", object())  # type: ignore[arg-type]


def test_client_requires_non_empty_workflow_id_for_updates() -> None:
    workflow = Workflow(name="demo")
    workflow.add_node(UppercaseNode("upper", UppercaseConfig(prefix="")))

    client = OrcheoClient(base_url="https://example.com")
    with pytest.raises(ValueError):
        client.build_deployment_request(workflow, workflow_id="  ")


def test_workflow_node_validations() -> None:
    class NoTypeNode(WorkflowNode[UppercaseConfig]):
        type_name = ""  # type: ignore[assignment]

    with pytest.raises(ValueError):
        NoTypeNode("valid", UppercaseConfig(prefix=""))

    with pytest.raises(ValueError):
        UppercaseNode(" ", UppercaseConfig(prefix=""))


def test_workflow_node_export_and_repr() -> None:
    node = UppercaseNode("upper", UppercaseConfig(prefix="Result: "))

    exported = node.export()
    assert exported == {"name": "upper", "type": "Uppercase", "prefix": "Result: "}
    assert "UppercaseNode" in repr(node)


def test_workflow_metadata_property_returns_copy() -> None:
    workflow = Workflow(name="demo", metadata={"team": "core"})
    metadata = workflow.metadata

    metadata["team"] = "mutated"
    assert workflow.metadata == {"team": "core"}


def test_workflow_requires_non_empty_name() -> None:
    with pytest.raises(ValueError):
        Workflow(name=" ")


def test_workflow_node_model_json_schema_exposes_config() -> None:
    node = UppercaseNode("upper", UppercaseConfig(prefix="Result: "))

    schema = node.model_json_schema()

    assert "properties" in schema
    assert "prefix" in schema["properties"]
