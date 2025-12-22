"""Simplified Slack mention responder workflow.

Configure Slack Events API to send requests to:
`/api/workflows/{workflow_id}/triggers/webhook?preserve_raw_body=true`
so signatures can be verified.

Configurable inputs:
- channel_id (single channel ID)
- slack_mention_reply (scripted response text)
- team_id (Slack workspace ID)
"""

from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from orcheo.edges import Condition, IfElse
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.slack import SlackEventsParserNode, SlackNode


class FormatReplyNode(TaskNode):
    """Build the scripted reply text for an app mention."""

    default_reply: str = "Thanks for the mention! We'll follow up soon."

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return the reply text, using configured overrides when present."""
        reply_text = self.default_reply
        config_state = state.get("config", {})
        if isinstance(config_state, dict):
            configurable = config_state.get("configurable", {})
            if isinstance(configurable, dict):
                configured_text = configurable.get("slack_mention_reply")
                if isinstance(configured_text, str) and configured_text.strip():
                    reply_text = configured_text.strip()

        results = state.get("results", {})
        user_id = None
        if isinstance(results, dict):
            slack_event = results.get("slack_events_parser", {})
            if isinstance(slack_event, dict):
                user_id = slack_event.get("user")

        if isinstance(user_id, str) and user_id.strip():
            reply_text = f"<@{user_id}> {reply_text}"

        return {"text": reply_text}


async def build_graph() -> StateGraph:
    """Build the simplified Slack mention responder workflow."""
    graph = StateGraph(State)
    graph.add_node(
        "slack_events_parser",
        SlackEventsParserNode(
            name="slack_events_parser",
            allowed_event_types=["app_mention"],
            channel_id="{{config.configurable.channel_id}}",
            timestamp_tolerance_seconds=10,
        ),
    )
    graph.add_node(
        "format_reply",
        FormatReplyNode(name="format_reply"),
    )
    graph.add_node(
        "post_reply",
        SlackNode(
            name="post_reply",
            tool_name="slack_post_message",
            team_id="{{config.configurable.team_id}}",
            kwargs={
                "channel_id": "{{slack_events_parser.channel}}",
                "text": "{{format_reply.text}}",
                "mrkdwn": True,
            },
        ),
    )

    graph.set_entry_point("slack_events_parser")
    graph.add_edge("slack_events_parser", "format_reply")

    reply_router = IfElse(
        name="reply_router",
        conditions=[
            Condition(
                left="{{slack_events_parser.should_process}}", operator="is_truthy"
            ),
        ],
    )
    graph.add_conditional_edges(
        "format_reply",
        reply_router,
        {
            "true": "post_reply",
            "false": END,
        },
    )
    graph.add_edge("post_reply", END)
    return graph
