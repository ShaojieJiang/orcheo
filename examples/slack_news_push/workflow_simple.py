"""Simplified Slack mention responder workflow with a scheduled message.

Configure Slack Events API to send requests to:
`/api/workflows/{workflow_id}/triggers/webhook?preserve_raw_body=true`
so signatures can be verified.

Configurable inputs:
- channel_id (single channel ID)
- slack_mention_reply (scripted response text)
- slack_scheduled_message (scheduled message text)
- team_id (Slack workspace ID)
"""

from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from orcheo.edges import Condition, IfElse
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.slack import SlackEventsParserNode, SlackNode
from orcheo.nodes.triggers import CronTriggerNode


class DetectTriggerNode(TaskNode):
    """Detect whether the workflow was invoked by a webhook payload."""

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return whether a webhook body is present in inputs."""
        inputs = state.get("inputs", {})
        has_webhook = bool(inputs.get("body"))
        return {"has_webhook": has_webhook}


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


class FormatScheduledMessageNode(TaskNode):
    """Build the scripted message text for scheduled posts."""

    default_message: str = "Scheduled update from Orcheo."

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return the scheduled message text from config when present."""
        message_text = self.default_message
        config_state = state.get("config", {})
        if isinstance(config_state, dict):
            configurable = config_state.get("configurable", {})
            if isinstance(configurable, dict):
                configured_text = configurable.get("slack_scheduled_message")
                if isinstance(configured_text, str) and configured_text.strip():
                    message_text = configured_text.strip()

        return {"text": message_text}


async def build_graph() -> StateGraph:
    """Build the simplified Slack mention responder workflow."""
    graph = StateGraph(State)
    graph.add_node("detect_trigger", DetectTriggerNode(name="detect_trigger"))
    graph.add_node(
        "cron_trigger",
        CronTriggerNode(
            name="cron_trigger",
            expression="* * * * *",
            timezone="UTC",
        ),
    )
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
        "format_scheduled_message",
        FormatScheduledMessageNode(name="format_scheduled_message"),
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
    graph.add_node(
        "post_scheduled_message",
        SlackNode(
            name="post_scheduled_message",
            tool_name="slack_post_message",
            team_id="{{config.configurable.team_id}}",
            kwargs={
                "channel_id": "{{config.configurable.channel_id}}",
                "text": "{{format_scheduled_message.text}}",
                "mrkdwn": True,
            },
        ),
    )

    graph.set_entry_point("detect_trigger")
    trigger_router = IfElse(
        name="trigger_router",
        conditions=[Condition(left="{{detect_trigger.has_webhook}}", operator="is_truthy")],
    )
    graph.add_conditional_edges(
        "detect_trigger",
        trigger_router,
        {
            "true": "slack_events_parser",
            "false": "cron_trigger",
        },
    )
    graph.add_edge("slack_events_parser", "format_reply")
    graph.add_edge("cron_trigger", "format_scheduled_message")
    graph.add_edge("format_scheduled_message", "post_scheduled_message")
    graph.add_edge("post_scheduled_message", END)

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
