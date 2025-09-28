"""Tests for Slack node."""

import os
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from orcheo.nodes.slack import SlackNode


@dataclass
class MockToolResult:
    """Mock dataclass for tool call results."""

    content: list[dict[str, Any]]
    is_error: bool
    error: str | None = None


@pytest.fixture
def slack_node():
    return SlackNode(
        name="slack_node",
        tool_name="slack_post_message",
        kwargs={"channel": "#general", "text": "Hello World!"},
    )


@pytest.mark.asyncio
async def test_slack_node_run_success(slack_node):
    """Test successful execution of SlackNode.run method."""
    # Mock the result from the tool call
    mock_result = MockToolResult(
        content=[{"text": "Message sent successfully"}], is_error=False
    )

    # Mock the client and its call_tool method
    mock_client = AsyncMock()
    mock_client.call_tool = AsyncMock(return_value=mock_result)

    # Mock the transport
    mock_transport = MagicMock()

    # Mock the async context manager
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_client)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "orcheo.nodes.slack.NpxStdioTransport", return_value=mock_transport
    ) as mock_transport_class:
        with patch(
            "orcheo.nodes.slack.Client", return_value=mock_context_manager
        ) as mock_client_class:
            with patch.dict(
                os.environ,
                {
                    "SLACK_BOT_TOKEN": "test_token",
                    "SLACK_TEAM_ID": "test_team",
                    "SLACK_CHANNEL_IDS": "test_channel_ids",
                },
            ):
                result = await slack_node.run({}, None)

                # Verify the transport was created with correct parameters
                mock_transport_class.assert_called_once_with(
                    "@modelcontextprotocol/server-slack",
                    env_vars={
                        "SLACK_BOT_TOKEN": "test_token",
                        "SLACK_TEAM_ID": "test_team",
                        "SLACK_CHANNEL_IDS": "test_channel_ids",
                    },
                )

                # Verify the client was created with the transport
                mock_client_class.assert_called_once_with(mock_transport)

                # Verify the tool was called with correct parameters
                mock_client.call_tool.assert_called_once_with(
                    "slack_post_message",
                    {"channel": "#general", "text": "Hello World!"},
                )

                # Verify the result is converted to dict
                assert result == {
                    "content": [{"text": "Message sent successfully"}],
                    "is_error": False,
                    "error": None,
                }


@pytest.mark.asyncio
async def test_slack_node_run_missing_env_vars(slack_node):
    """Test SlackNode.run with missing environment variables."""
    mock_result = MockToolResult(content=[{"text": "Success"}], is_error=False)

    mock_client = AsyncMock()
    mock_client.call_tool = AsyncMock(return_value=mock_result)

    mock_transport = MagicMock()

    # Mock the async context manager
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_client)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "orcheo.nodes.slack.NpxStdioTransport", return_value=mock_transport
    ) as mock_transport_class:
        with patch("orcheo.nodes.slack.Client", return_value=mock_context_manager):
            with patch.dict(os.environ, {}, clear=True):
                await slack_node.run({}, None)

                # Verify environment variables default to empty strings
                mock_transport_class.assert_called_once_with(
                    "@modelcontextprotocol/server-slack",
                    env_vars={
                        "SLACK_BOT_TOKEN": "",
                        "SLACK_TEAM_ID": "",
                        "SLACK_CHANNEL_IDS": "",
                    },
                )


@pytest.mark.asyncio
async def test_slack_node_run_different_tool(slack_node):
    """Test SlackNode.run with different tool and kwargs."""
    # Update the node with different tool and kwargs
    slack_node.tool_name = "slack_list_channels"
    slack_node.kwargs = {"limit": 10}

    mock_result = MockToolResult(
        content=[{"channels": ["#general", "#random"]}], is_error=False
    )

    mock_client = AsyncMock()
    mock_client.call_tool = AsyncMock(return_value=mock_result)

    mock_transport = MagicMock()

    # Mock the async context manager
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_client)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)

    with patch("orcheo.nodes.slack.NpxStdioTransport", return_value=mock_transport):
        with patch("orcheo.nodes.slack.Client", return_value=mock_context_manager):
            with patch.dict(
                os.environ,
                {
                    "SLACK_BOT_TOKEN": "test_token",
                    "SLACK_TEAM_ID": "test_team",
                    "SLACK_CHANNEL_IDS": "test_channel_ids",
                },
            ):
                result = await slack_node.run({}, None)

                # Verify the correct tool was called with correct kwargs
                mock_client.call_tool.assert_called_once_with(
                    "slack_list_channels", {"limit": 10}
                )

                assert result == {
                    "content": [{"channels": ["#general", "#random"]}],
                    "is_error": False,
                    "error": None,
                }


@pytest.mark.asyncio
async def test_slack_node_run_error_case(slack_node):
    """Test SlackNode.run when tool call results in error."""
    mock_result = MockToolResult(content=[], is_error=True, error="Channel not found")

    mock_client = AsyncMock()
    mock_client.call_tool = AsyncMock(return_value=mock_result)

    mock_transport = MagicMock()

    # Mock the async context manager
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_client)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)

    with patch("orcheo.nodes.slack.NpxStdioTransport", return_value=mock_transport):
        with patch("orcheo.nodes.slack.Client", return_value=mock_context_manager):
            with patch.dict(
                os.environ,
                {
                    "SLACK_BOT_TOKEN": "test_token",
                    "SLACK_TEAM_ID": "test_team",
                    "SLACK_CHANNEL_IDS": "test_channel_ids",
                },
            ):
                result = await slack_node.run({}, None)

                # Verify error result is properly returned
                assert result == {
                    "content": [],
                    "is_error": True,
                    "error": "Channel not found",
                }


@pytest.mark.asyncio
async def test_slack_node_run_empty_kwargs(slack_node):
    """Test SlackNode.run with empty kwargs."""
    # Update the node with empty kwargs
    slack_node.kwargs = {}

    mock_result = MockToolResult(content=[{"text": "Success"}], is_error=False)

    mock_client = AsyncMock()
    mock_client.call_tool = AsyncMock(return_value=mock_result)

    mock_transport = MagicMock()

    # Mock the async context manager
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_client)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)

    with patch("orcheo.nodes.slack.NpxStdioTransport", return_value=mock_transport):
        with patch("orcheo.nodes.slack.Client", return_value=mock_context_manager):
            with patch.dict(
                os.environ,
                {
                    "SLACK_BOT_TOKEN": "test_token",
                    "SLACK_TEAM_ID": "test_team",
                    "SLACK_CHANNEL_IDS": "test_channel_ids",
                },
            ):
                result = await slack_node.run({}, None)

                # Verify the tool was called with empty kwargs
                mock_client.call_tool.assert_called_once_with("slack_post_message", {})

                assert result == {
                    "content": [{"text": "Success"}],
                    "is_error": False,
                    "error": None,
                }
