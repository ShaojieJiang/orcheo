"""Tests for ChatKit helper functions."""

from __future__ import annotations
from typing import Any
from chatkit.types import (
    AssistantMessageContent,
    UserMessageContent,
    UserMessageTextContent,
)
from langchain_core.messages import AIMessage, HumanMessage
from orcheo_backend.app.chatkit.message_utils import (
    build_initial_state,
    collect_text_from_assistant_content,
    collect_text_from_user_content,
    extract_reply_from_state,
    stringify_langchain_message,
)


def testcollect_text_from_user_content_empty() -> None:
    """Empty user content returns empty string."""
    content: list[UserMessageContent] = []
    result = collect_text_from_user_content(content)
    assert result == ""


def testcollect_text_from_user_content_single() -> None:
    """Single text content is extracted."""
    content: list[UserMessageContent] = [
        UserMessageTextContent(type="input_text", text="Hello world")
    ]
    result = collect_text_from_user_content(content)
    assert result == "Hello world"


def testcollect_text_from_user_content_multiple() -> None:
    """Multiple text contents are joined with spaces."""
    content: list[UserMessageContent] = [
        UserMessageTextContent(type="input_text", text="Hello"),
        UserMessageTextContent(type="input_text", text="world"),
    ]
    result = collect_text_from_user_content(content)
    assert result == "Hello world"


def testcollect_text_from_assistant_content_empty() -> None:
    """Empty assistant content returns empty string."""
    content: list[AssistantMessageContent] = []
    result = collect_text_from_assistant_content(content)
    assert result == ""


def testcollect_text_from_assistant_content_single() -> None:
    """Single assistant content is extracted."""
    content = [AssistantMessageContent(text="Response")]
    result = collect_text_from_assistant_content(content)
    assert result == "Response"


def testcollect_text_from_assistant_content_multiple() -> None:
    """Multiple assistant contents are joined."""
    content = [
        AssistantMessageContent(text="Part 1"),
        AssistantMessageContent(text="Part 2"),
    ]
    result = collect_text_from_assistant_content(content)
    assert result == "Part 1 Part 2"


def teststringify_langchain_message_string() -> None:
    """String content is returned as-is."""
    message = HumanMessage(content="Hello")
    result = stringify_langchain_message(message)
    assert result == "Hello"


def teststringify_langchain_message_dict() -> None:
    """Dict with content key is extracted."""
    message = {"content": "Hello from dict"}
    result = stringify_langchain_message(message)
    assert result == "Hello from dict"


def teststringify_langchain_message_dict_with_text() -> None:
    """Dict with text key is extracted."""
    message = {"text": "Hello from text"}
    result = stringify_langchain_message(message)
    assert result == "Hello from text"


def teststringify_langchain_message_list() -> None:
    """List content is joined."""
    message = AIMessage(content=["Part 1", "Part 2", "Part 3"])
    result = stringify_langchain_message(message)
    assert result == "Part 1 Part 2 Part 3"


def teststringify_langchain_message_nested_list() -> None:
    """Nested list content is flattened."""
    message = AIMessage(
        content=[
            {"type": "text", "text": "Hello"},
            {"type": "text", "text": "world"},
        ]
    )
    result = stringify_langchain_message(message)
    assert "Hello" in result and "world" in result


def testbuild_initial_state_langgraph_script() -> None:
    """LangGraph script format returns inputs as dict."""
    graph_config = {"format": "langgraph-script"}
    inputs = {"message": "test", "count": 42}
    result = build_initial_state(graph_config, inputs)
    assert result["message"] == "test"
    assert result["count"] == 42
    assert result["inputs"] == inputs
    assert result["messages"] == []
    assert result["results"] == {}


def testbuild_initial_state_default() -> None:
    """Default format returns structured state with messages, results, inputs."""
    graph_config: dict[str, Any] = {}
    inputs = {"message": "test"}
    result = build_initial_state(graph_config, inputs)
    assert result["messages"] == []
    assert result["results"] == {}
    assert result["inputs"] == {"message": "test"}


def testextract_reply_from_state_direct_reply() -> None:
    """Direct reply key is extracted."""
    state = {"reply": "Direct reply"}
    result = extract_reply_from_state(state)
    assert result == "Direct reply"


def testextract_reply_from_state_none_reply() -> None:
    """None reply is handled."""
    state = {"reply": None, "results": {"output": "Fallback"}}
    result = extract_reply_from_state(state)
    assert result == "Fallback"


def testextract_reply_from_state_results_with_reply() -> None:
    """Reply nested in results is extracted."""
    state = {
        "results": {
            "node1": {"reply": "Nested reply"},
        }
    }
    result = extract_reply_from_state(state)
    assert result == "Nested reply"


def testextract_reply_from_state_results_string() -> None:
    """String value in results is returned."""
    state = {
        "results": {
            "output": "String result",
        }
    }
    result = extract_reply_from_state(state)
    assert result == "String result"


def testextract_reply_from_state_messages() -> None:
    """Last message in messages is extracted."""
    state = {
        "messages": [
            HumanMessage(content="Hello"),
            AIMessage(content="Response from AI"),
        ]
    }
    result = extract_reply_from_state(state)
    assert result == "Response from AI"


def testextract_reply_from_state_no_reply() -> None:
    """Returns None when no reply can be extracted."""
    state = {"other": "data"}
    result = extract_reply_from_state(state)
    assert result is None


def testextract_reply_from_state_empty_messages() -> None:
    """Returns None for empty messages list."""
    state = {"messages": []}
    result = extract_reply_from_state(state)
    assert result is None
