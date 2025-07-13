"""Slack node."""

import os
from dataclasses import asdict
from typing import Literal
from fastmcp import Client
from fastmcp.client.transports import NpxStdioTransport
from langchain_core.runnables import RunnableConfig
from aic_flow.graph.state import State
from aic_flow.nodes.base import TaskNode
from aic_flow.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="SlackNode",
        description="Slack node",
        category="slack",
    )
)
class SlackNode(TaskNode):
    """Slack node.

    To use this node, you need to set the following environment variables:
    - SLACK_BOT_TOKEN: Required. The Bot User OAuth Token starting with xoxb-.
    - SLACK_TEAM_ID: Required. Your Slack workspace ID starting with T.
    - SLACK_CHANNEL_IDS: Optional. Comma-separated list of channel IDs to limit
    channel access (e.g., "C01234567, C76543210"). If not set, all public
    channels will be listed.
    """

    tool_name: Literal[
        "slack_list_channels",
        "slack_post_message",
        "slack_reply_to_thread",
        "slack_add_reaction",
        "slack_get_channel_history",
        "slack_get_thread_replies",
        "slack_get_users",
        "slack_get_user_profile",
    ]
    """The name of the tool supported by the MCP server."""
    kwargs: dict = {}
    """The keyword arguments to pass to the tool."""

    async def run(self, state: State, config: RunnableConfig) -> dict:
        """Run the Slack node."""
        transport = NpxStdioTransport(
            "@modelcontextprotocol/server-slack",
            env_vars={
                "SLACK_BOT_TOKEN": os.getenv("SLACK_BOT_TOKEN", ""),
                "SLACK_TEAM_ID": os.getenv("SLACK_TEAM_ID", ""),
            },
        )
        async with Client(transport) as client:
            result = await client.call_tool(self.tool_name, self.kwargs)

            return asdict(result)
