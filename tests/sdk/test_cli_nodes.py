"""Tests for CLI node commands."""

from __future__ import annotations
from typer.testing import CliRunner
from orcheo_sdk.cli.main import app


def test_node_list_shows_registered_nodes(
    runner: CliRunner, env: dict[str, str]
) -> None:
    result = runner.invoke(app, ["node", "list"], env=env)
    assert result.exit_code == 0
    assert "WebhookTriggerNode" in result.stdout
    assert "TaskNode" in result.stdout


def test_node_show_displays_schema(runner: CliRunner, env: dict[str, str]) -> None:
    result = runner.invoke(app, ["node", "show", "AgentNode"], env=env)
    assert result.exit_code == 0
    assert "AgentNode" in result.stdout


def test_node_list_with_tag_filter(runner: CliRunner, env: dict[str, str]) -> None:
    result = runner.invoke(app, ["node", "list", "--tag", "trigger"], env=env)
    assert result.exit_code == 0
    assert "WebhookTriggerNode" in result.stdout


def test_node_show_nonexistent_error(runner: CliRunner, env: dict[str, str]) -> None:
    result = runner.invoke(app, ["node", "show", "NonexistentNode"], env=env)
    assert result.exit_code != 0


def test_node_show_no_schema_info(runner: CliRunner, env: dict[str, str]) -> None:
    """Test node show with node that has neither schema nor attributes."""
    from orcheo.nodes.registry import NodeMetadata, registry

    # Register a test node without model_json_schema and without annotations
    test_meta = NodeMetadata(
        name="TestNodeNoInfo",
        description="Test node without schema",
        category="test",
    )

    class TestNodeNoInfo:
        """Node without model_json_schema and no annotations."""

        pass

    # Register the test node
    registry._nodes["TestNodeNoInfo"] = TestNodeNoInfo
    registry._metadata["TestNodeNoInfo"] = test_meta

    try:
        result = runner.invoke(app, ["node", "show", "TestNodeNoInfo"], env=env)
        assert result.exit_code == 0
        assert "TestNodeNoInfo" in result.stdout
        assert "No schema information available" in result.stdout
    finally:
        # Clean up
        registry._nodes.pop("TestNodeNoInfo", None)
        registry._metadata.pop("TestNodeNoInfo", None)


def test_node_show_with_attributes_only(runner: CliRunner, env: dict[str, str]) -> None:
    """Test node show with node that has attributes but no model_json_schema."""
    from orcheo.nodes.registry import NodeMetadata, registry

    # Register a test node with annotations but no model_json_schema
    test_meta = NodeMetadata(
        name="TestNodeWithAttrs",
        description="Test node with attributes",
        category="test",
    )

    class TestNodeWithAttrs:
        """Node with annotations but no model_json_schema."""

        test_attr: str
        count: int

    # Register the test node
    registry._nodes["TestNodeWithAttrs"] = TestNodeWithAttrs
    registry._metadata["TestNodeWithAttrs"] = test_meta

    try:
        result = runner.invoke(app, ["node", "show", "TestNodeWithAttrs"], env=env)
        assert result.exit_code == 0
        assert "TestNodeWithAttrs" in result.stdout
        assert "test_attr" in result.stdout
        assert "count" in result.stdout
    finally:
        # Clean up
        registry._nodes.pop("TestNodeWithAttrs", None)
        registry._metadata.pop("TestNodeWithAttrs", None)
