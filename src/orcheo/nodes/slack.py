"""Slack node."""

from dataclasses import asdict
from typing import Literal
from fastmcp import Client
from fastmcp.client.transports import NpxStdioTransport
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


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
    bot_token: str = "[[slack_bot_token]]"
    """Bot user OAuth token."""
    team_id: str = "[[slack_team_id]]"
    """Slack workspace ID."""
    channel_ids: str | None = None
    """Optional comma separated list of channel IDs."""

    async def run(self, state: State, config: RunnableConfig) -> dict:
        """Run the Slack node."""
        env_vars = {
            "SLACK_BOT_TOKEN": self.bot_token,
            "SLACK_TEAM_ID": self.team_id,
        }
        if self.channel_ids:
            env_vars["SLACK_CHANNEL_IDS"] = self.channel_ids
        transport = NpxStdioTransport(
            "@modelcontextprotocol/server-slack",
            env_vars=env_vars,
        )
        async with Client(transport) as client:
            result = await client.call_tool(self.tool_name, self.kwargs)

            return asdict(result)
