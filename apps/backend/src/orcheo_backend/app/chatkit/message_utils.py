"""Helper utilities for working with ChatKit and LangChain message payloads."""

from __future__ import annotations
from collections.abc import Mapping
from typing import Any
from chatkit.types import (
    AssistantMessageContent,
    UserMessageContent,
)
from langchain_core.messages import BaseMessage
from orcheo.graph.ingestion import LANGGRAPH_SCRIPT_FORMAT


def collect_text_from_user_content(content: list[UserMessageContent]) -> str:
    """Return concatenated text segments from user message content."""
    parts: list[str] = []
    for item in content:
        text = getattr(item, "text", None)
        if text:
            parts.append(str(text))
    return " ".join(parts).strip()


def collect_text_from_assistant_content(
    content: list[AssistantMessageContent],
) -> str:
    """Return concatenated text segments from assistant message content."""
    parts: list[str] = []
    for item in content:
        if item.text:
            parts.append(str(item.text))
    return " ".join(parts).strip()


def stringify_langchain_message(message: Any) -> str:
    """Convert LangChain message objects into a plain string."""
    value: Any
    if isinstance(message, BaseMessage):
        value = message.content
    elif isinstance(message, Mapping):
        value = message.get("content") or message.get("text")
    else:
        value = getattr(message, "content", message)

    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for entry in value:
            part = stringify_langchain_message(entry)
            if part:
                parts.append(part)
        return " ".join(parts)
    return str(value)


def build_initial_state(
    graph_config: Mapping[str, Any],
    inputs: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Create the initial workflow state for the configured format."""
    if graph_config.get("format") == LANGGRAPH_SCRIPT_FORMAT:
        state = dict(inputs)
        state.setdefault("inputs", dict(inputs))
        state.setdefault("results", {})
        state.setdefault("messages", [])
        return state
    return {
        "messages": [],
        "results": {},
        "inputs": dict(inputs),
    }


def extract_reply_from_state(state: Mapping[str, Any]) -> str | None:
    """Attempt to pull an assistant reply from the workflow state."""
    if "reply" in state:
        reply = state["reply"]
        if reply is not None:
            return str(reply)

    results = state.get("results")
    if isinstance(results, Mapping):
        for value in results.values():
            if isinstance(value, Mapping) and "reply" in value:
                reply = value["reply"]
                if reply is not None:
                    return str(reply)
            if isinstance(value, str):
                return value

    messages = state.get("messages")
    if isinstance(messages, list) and messages:
        return stringify_langchain_message(messages[-1])

    return None


__all__ = [
    "build_initial_state",
    "collect_text_from_assistant_content",
    "collect_text_from_user_content",
    "extract_reply_from_state",
    "stringify_langchain_message",
]
