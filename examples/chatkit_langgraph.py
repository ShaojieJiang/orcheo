"""LangGraph workflow tailored for ChatKit-triggered conversations.

This script demonstrates how to build a minimal LangGraph workflow that can
be ingested into the Orcheo backend and triggered from the OpenAI ChatKit
interface. The graph expects the backend to forward an input payload containing
at least a ``message`` field (as produced by the ChatKit client tool trigger).

Nodes in the workflow:
- ``normalize_message``: sanitize and normalize the inbound text
- ``classify_intent``: derive a coarse intent label from the message
- ``compose_reply``: craft the final textual reply surfaced back to ChatKit

To ingest this workflow into the Orcheo backend, run the
``examples/ingest_langgraph.py`` helper or register it via the SDK/CLI by
providing ``build_graph`` as the entrypoint.
"""

from __future__ import annotations
from typing import Any
from langgraph.graph import StateGraph


State = dict[str, Any]


def normalize_message(state: State) -> State:
    """Normalize the inbound message from ChatKit."""
    raw_message = state.get("message")
    if raw_message is None:
        normalized = ""
    else:
        normalized = str(raw_message).strip()

    # Provide a friendly default when the user sends an empty composer event.
    if not normalized:
        normalized = "Hello there!"

    return {
        "normalized_message": normalized,
    }


def classify_intent(state: State) -> State:
    """Assign a lightweight intent label based on the normalized text."""
    message = str(state.get("normalized_message", "")).lower()

    if not message:
        intent = "no_input"
    elif any(greeting in message for greeting in ("hello", "hi", "hey")):
        intent = "greeting"
    elif "help" in message or "support" in message:
        intent = "support"
    elif "thanks" in message or "thank you" in message:
        intent = "gratitude"
    else:
        intent = "general"

    return {
        "intent": intent,
    }


def compose_reply(state: State) -> State:
    """Craft a conversational reply that ChatKit can surface."""
    message = str(state.get("normalized_message", ""))
    intent = str(state.get("intent", "general"))

    if intent == "greeting":
        reply = "Hi there! I'm ready to help you explore your workflow."
    elif intent == "support":
        reply = (
            "It sounds like you need a hand. Share a bit more detail and "
            "I'll outline the next steps."
        )
    elif intent == "gratitude":
        reply = "You're very welcome! Let me know if there's anything else."
    elif intent == "no_input":
        reply = (
            "I didn't catch a message. Try typing a question or describe "
            "what you'd like the workflow to do."
        )
    else:
        reply = (
            "Thanks for the message! I'll route this through the workflow "
            "so you can review the results in Orcheo."
        )

    return {
        "reply": reply,
        "echo": message,
        "intent": intent,
    }


def build_graph() -> StateGraph:
    """Construct and return the LangGraph workflow."""
    graph = StateGraph(dict)
    graph.add_node("normalize_message", normalize_message)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("compose_reply", compose_reply)

    graph.add_edge("normalize_message", "classify_intent")
    graph.add_edge("classify_intent", "compose_reply")

    graph.set_entry_point("normalize_message")
    graph.set_finish_point("compose_reply")
    return graph


if __name__ == "__main__":
    compiled = build_graph().compile()
    payload = {"message": "Hello! Can you help me run the pipeline?"}
    result = compiled.invoke(payload)
    print(result)
    print(f"Chat reply: {result['reply']}")
