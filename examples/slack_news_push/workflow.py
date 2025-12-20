"""Slack news push workflow example."""

from __future__ import annotations
from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from orcheo.edges import Condition, IfElse
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.mongodb import (
    MongoDBAggregateNode,
    MongoDBFindNode,
    MongoDBUpdateManyNode,
)
from orcheo.nodes.slack import SlackEventsParserNode, SlackNode


CHANNEL_ID = "C0946SY4TTM"
DATABASE = "Orcheo"
COLLECTION = "rss_feeds"
ITEM_LIMIT = 30


class DetectTriggerNode(TaskNode):
    """Detect whether the workflow was invoked by a webhook payload."""

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return whether a webhook body is present in inputs."""
        inputs = state.get("inputs", {})
        has_webhook = bool(inputs.get("body"))
        return {"has_webhook": has_webhook}


class FormatDigestNode(TaskNode):
    """Format unread items into a Slack digest message."""

    @staticmethod
    def _decode_title(text: str | None) -> str:
        if not text:
            return "No Title"
        return (
            text.replace("&quot;", '"')
            .replace("&apos;", "'")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&amp;", "&")
            .replace("&nbsp;", " ")
            .replace("<", "[")
            .replace(">", "]")
        )

    @staticmethod
    def _read_items(state: State) -> list[dict[str, Any]]:
        results = state.get("results", {})
        if not isinstance(results, dict):
            return []
        find_result = results.get("find_unread", {})
        if not isinstance(find_result, dict):
            return []
        data = find_result.get("data")
        if isinstance(data, list):
            return data
        return []

    @staticmethod
    def _read_unread_count(state: State) -> int:
        results = state.get("results", {})
        if not isinstance(results, dict):
            return 0
        count_result = results.get("count_unread", {})
        if not isinstance(count_result, dict):
            return 0
        data = count_result.get("data")
        if not isinstance(data, list) or not data:
            return 0
        count = data[0].get("unread_count", 0)
        return int(count or 0)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return Slack-formatted digest text and item IDs."""
        items = self._read_items(state)
        total_unread = self._read_unread_count(state)

        lines = []
        for item in items:
            title = self._decode_title(item.get("title"))
            url = item.get("link", "")
            lines.append(f"* <{url}|{title}>")

        remaining = max(total_unread - len(items), 0)
        body = "\n".join(lines)
        if body:
            body = f"{body}\n"

        news = f"{body}Unread count: {remaining}"
        return {
            "news": news,
            "ids": [item.get("_id") for item in items],
        }


def build_graph() -> StateGraph:
    """Build the Slack news push workflow graph."""
    graph = StateGraph(State)

    graph.add_node("detect_trigger", DetectTriggerNode(name="detect_trigger"))
    graph.add_node(
        "slack_events_parser",
        SlackEventsParserNode(
            name="slack_events_parser",
            channel_id=CHANNEL_ID,
        ),
    )
    graph.add_node(
        "count_unread",
        MongoDBAggregateNode(
            name="count_unread",
            database=DATABASE,
            collection=COLLECTION,
            pipeline=[{"$match": {"read": False}}, {"$count": "unread_count"}],
        ),
    )
    graph.add_node(
        "find_unread",
        MongoDBFindNode(
            name="find_unread",
            database=DATABASE,
            collection=COLLECTION,
            filter={"read": False},
            sort={"isoDate": -1},
            limit=ITEM_LIMIT,
        ),
    )
    graph.add_node("format_digest", FormatDigestNode(name="format_digest"))
    graph.add_node(
        "post_message",
        SlackNode(
            name="post_message",
            tool_name="slack_post_message",
            kwargs={
                "channel_id": CHANNEL_ID,
                "text": "{{format_digest.news}}",
                "mrkdwn": True,
            },
        ),
    )
    graph.add_node(
        "mark_read",
        MongoDBUpdateManyNode(
            name="mark_read",
            database=DATABASE,
            collection=COLLECTION,
            filter={"_id": {"$in": "{{format_digest.ids}}"}},
            update={"$set": {"read": True}},
        ),
    )

    graph.set_entry_point("detect_trigger")

    trigger_router = IfElse(
        name="trigger_router",
        conditions=[
            Condition(left="{{detect_trigger.has_webhook}}", operator="is_truthy")
        ],
    )
    graph.add_conditional_edges(
        "detect_trigger",
        trigger_router,
        {
            "true": "slack_events_parser",
            "false": "count_unread",
        },
    )

    process_router = IfElse(
        name="process_router",
        conditions=[
            Condition(
                left="{{slack_events_parser.should_process}}", operator="is_truthy"
            )
        ],
    )
    graph.add_conditional_edges(
        "slack_events_parser",
        process_router,
        {
            "true": "count_unread",
            "false": END,
        },
    )

    graph.add_edge("count_unread", "find_unread")
    graph.add_edge("find_unread", "format_digest")
    graph.add_edge("format_digest", "post_message")

    post_router = IfElse(
        name="post_router",
        conditions=[Condition(left="{{post_message.is_error}}", operator="is_falsy")],
    )
    graph.add_conditional_edges(
        "post_message",
        post_router,
        {
            "true": "mark_read",
            "false": END,
        },
    )
    graph.add_edge("mark_read", END)

    return graph


__all__ = ["build_graph"]
