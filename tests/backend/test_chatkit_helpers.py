"""Tests for ChatKit helper functions."""

from __future__ import annotations
from typing import Any
from chatkit.types import (
    AssistantMessageContent,
    UserMessageContent,
    UserMessageTextContent,
)
from langchain_core.messages import AIMessage, HumanMessage
from orcheo_backend.app.chatkit_service import (
    _build_initial_state,
    _collect_text_from_assistant_content,
    _collect_text_from_user_content,
    _extract_reply_from_state,
    _stringify_langchain_message,
)


def test_collect_text_from_user_content_empty() -> None:
    """Empty user content returns empty string."""
    content: list[UserMessageContent] = []
    result = _collect_text_from_user_content(content)
    assert result == ""


def test_collect_text_from_user_content_single() -> None:
    """Single text content is extracted."""
    content: list[UserMessageContent] = [
        UserMessageTextContent(type="input_text", text="Hello world")
    ]
    result = _collect_text_from_user_content(content)
    assert result == "Hello world"


def test_collect_text_from_user_content_multiple() -> None:
    """Multiple text contents are joined with spaces."""
    content: list[UserMessageContent] = [
        UserMessageTextContent(type="input_text", text="Hello"),
        UserMessageTextContent(type="input_text", text="world"),
    ]
    result = _collect_text_from_user_content(content)
    assert result == "Hello world"


def test_collect_text_from_assistant_content_empty() -> None:
    """Empty assistant content returns empty string."""
    content: list[AssistantMessageContent] = []
    result = _collect_text_from_assistant_content(content)
    assert result == ""


def test_collect_text_from_assistant_content_single() -> None:
    """Single assistant content is extracted."""
    content = [AssistantMessageContent(text="Response")]
    result = _collect_text_from_assistant_content(content)
    assert result == "Response"


def test_collect_text_from_assistant_content_multiple() -> None:
    """Multiple assistant contents are joined."""
    content = [
        AssistantMessageContent(text="Part 1"),
        AssistantMessageContent(text="Part 2"),
    ]
    result = _collect_text_from_assistant_content(content)
    assert result == "Part 1 Part 2"


def test_stringify_langchain_message_string() -> None:
    """String content is returned as-is."""
    message = HumanMessage(content="Hello")
    result = _stringify_langchain_message(message)
    assert result == "Hello"


def test_stringify_langchain_message_dict() -> None:
    """Dict with content key is extracted."""
    message = {"content": "Hello from dict"}
    result = _stringify_langchain_message(message)
    assert result == "Hello from dict"


def test_stringify_langchain_message_dict_with_text() -> None:
    """Dict with text key is extracted."""
    message = {"text": "Hello from text"}
    result = _stringify_langchain_message(message)
    assert result == "Hello from text"


def test_stringify_langchain_message_list() -> None:
    """List content is joined."""
    message = AIMessage(content=["Part 1", "Part 2", "Part 3"])
    result = _stringify_langchain_message(message)
    assert result == "Part 1 Part 2 Part 3"


def test_stringify_langchain_message_nested_list() -> None:
    """Nested list content is flattened."""
    message = AIMessage(
        content=[
            {"type": "text", "text": "Hello"},
            {"type": "text", "text": "world"},
        ]
    )
    result = _stringify_langchain_message(message)
    assert "Hello" in result and "world" in result


def test_build_initial_state_langgraph_script() -> None:
    """LangGraph script format returns inputs as dict."""
    graph_config = {"format": "langgraph-script"}
    inputs = {"message": "test", "count": 42}
    result = _build_initial_state(graph_config, inputs)
    assert result == {"message": "test", "count": 42}


def test_build_initial_state_default() -> None:
    """Default format returns structured state with messages, results, inputs."""
    graph_config: dict[str, Any] = {}
    inputs = {"message": "test"}
    result = _build_initial_state(graph_config, inputs)
    assert result["messages"] == []
    assert result["results"] == {}
    assert result["inputs"] == {"message": "test"}


def test_extract_reply_from_state_direct_reply() -> None:
    """Direct reply key is extracted."""
    state = {"reply": "Direct reply"}
    result = _extract_reply_from_state(state)
    assert result == "Direct reply"


def test_extract_reply_from_state_none_reply() -> None:
    """None reply is handled."""
    state = {"reply": None, "results": {"output": "Fallback"}}
    result = _extract_reply_from_state(state)
    assert result == "Fallback"


def test_extract_reply_from_state_results_with_reply() -> None:
    """Reply nested in results is extracted."""
    state = {
        "results": {
            "node1": {"reply": "Nested reply"},
        }
    }
    result = _extract_reply_from_state(state)
    assert result == "Nested reply"


def test_extract_reply_from_state_results_string() -> None:
    """String value in results is returned."""
    state = {
        "results": {
            "output": "String result",
        }
    }
    result = _extract_reply_from_state(state)
    assert result == "String result"


def test_extract_reply_from_state_messages() -> None:
    """Last message in messages is extracted."""
    state = {
        "messages": [
            HumanMessage(content="Hello"),
            AIMessage(content="Response from AI"),
        ]
    }
    result = _extract_reply_from_state(state)
    assert result == "Response from AI"


def test_extract_reply_from_state_no_reply() -> None:
    """Returns None when no reply can be extracted."""
    state = {"other": "data"}
    result = _extract_reply_from_state(state)
    assert result is None


def test_extract_reply_from_state_empty_messages() -> None:
    """Returns None for empty messages list."""
    state = {"messages": []}
    result = _extract_reply_from_state(state)
    assert result is None
