"""Tests for helper functions in the ChatKit service module."""

from __future__ import annotations
from chatkit.types import AssistantMessageContent, UserMessageTextContent
from langchain_core.messages import AIMessage, HumanMessage
from orcheo.graph.ingestion import LANGGRAPH_SCRIPT_FORMAT
from orcheo_backend.app.chatkit.message_utils import (
    build_initial_state,
    collect_text_from_assistant_content,
    collect_text_from_user_content,
    extract_reply_from_state,
    stringify_langchain_message,
)


def teststringify_langchain_message_with_base_message() -> None:
    msg = HumanMessage(content="Hello world")
    result = stringify_langchain_message(msg)
    assert result == "Hello world"


def teststringify_langchain_message_with_mapping() -> None:
    msg = {"content": "Test content"}
    result = stringify_langchain_message(msg)
    assert result == "Test content"

    msg_with_text = {"text": "Test text"}
    result = stringify_langchain_message(msg_with_text)
    assert result == "Test text"


def teststringify_langchain_message_with_list() -> None:
    msg = HumanMessage(content=["Hello", "world"])
    result = stringify_langchain_message(msg)
    assert result == "Hello world"


def teststringify_langchain_message_with_nested_list() -> None:
    msg = {"content": [{"text": "Part 1"}, {"text": "Part 2"}]}
    result = stringify_langchain_message(msg)
    assert "Part 1" in result
    assert "Part 2" in result


def teststringify_langchain_message_with_object() -> None:
    class CustomMessage:
        content = "Custom content"

    msg = CustomMessage()
    result = stringify_langchain_message(msg)
    assert result == "Custom content"


def teststringify_langchain_message_with_plain_string() -> None:
    result = stringify_langchain_message("plain string")
    assert result == "plain string"


def teststringify_langchain_message_with_none_content() -> None:
    class EmptyMessage:
        pass

    msg = EmptyMessage()
    result = stringify_langchain_message(msg)
    assert result is not None


def teststringify_langchain_message_with_empty_list_entries() -> None:
    msg = {"content": ["", {"text": ""}, {"content": "Valid"}, None]}
    result = stringify_langchain_message(msg)
    assert "Valid" in result


def test_build_initial_state_langgraph_format() -> None:
    graph_config = {"format": LANGGRAPH_SCRIPT_FORMAT}
    inputs = {"message": "Hello", "metadata": {"key": "value"}}
    result = build_initial_state(graph_config, inputs)
    assert result == inputs


def test_build_initial_state_standard_format() -> None:
    graph_config = {"format": "standard"}
    inputs = {"message": "Hello"}
    result = build_initial_state(graph_config, inputs)

    assert "messages" in result
    assert "results" in result
    assert "inputs" in result
    assert result["inputs"] == inputs


def test_collect_text_from_user_content_multiple_parts() -> None:
    content = [
        UserMessageTextContent(type="input_text", text="Part 1"),
        UserMessageTextContent(type="input_text", text="Part 2"),
    ]
    result = collect_text_from_user_content(content)
    assert result == "Part 1 Part 2"


def test_collect_text_from_assistant_content_multiple_parts() -> None:
    content = [
        AssistantMessageContent(text="Response 1"),
        AssistantMessageContent(text="Response 2"),
    ]
    result = collect_text_from_assistant_content(content)
    assert result == "Response 1 Response 2"


def test_collect_text_from_user_content_with_no_text() -> None:
    class ContentWithoutText:
        pass

    content = [ContentWithoutText()]
    result = collect_text_from_user_content(content)
    assert result == ""


def test_collect_text_from_assistant_content_with_no_text() -> None:
    content = [AssistantMessageContent(text="")]
    result = collect_text_from_assistant_content(content)
    assert result == ""


def testextract_reply_from_state_with_reply_key() -> None:
    state = {"reply": "Direct reply"}
    result = extract_reply_from_state(state)
    assert result == "Direct reply"


def testextract_reply_from_state_with_none_reply() -> None:
    state = {"reply": None, "messages": [{"content": "Message content"}]}
    result = extract_reply_from_state(state)
    assert result is not None


def testextract_reply_from_state_from_results_dict() -> None:
    state = {"results": {"node_a": {"reply": "Reply from results"}}}
    result = extract_reply_from_state(state)
    assert result == "Reply from results"


def testextract_reply_from_state_from_results_string() -> None:
    state = {"results": {"node_a": "String result"}}
    result = extract_reply_from_state(state)
    assert result == "String result"


def testextract_reply_from_state_from_messages() -> None:
    state = {"messages": [AIMessage(content="AI response")]}
    result = extract_reply_from_state(state)
    assert result == "AI response"


def testextract_reply_from_state_returns_none() -> None:
    state = {"unrelated": "data"}
    result = extract_reply_from_state(state)
    assert result is None


def testextract_reply_from_state_with_results_non_string_value() -> None:
    state = {"results": {"node_a": {"other": "value"}}}
    result = extract_reply_from_state(state)
    assert result is None


def testextract_reply_from_state_with_empty_messages() -> None:
    state = {"messages": []}
    result = extract_reply_from_state(state)
    assert result is None


def testextract_reply_from_state_with_none_reply_in_results() -> None:
    state = {"results": {"node_a": {"reply": None}, "node_b": "fallback"}}
    result = extract_reply_from_state(state)
    assert result == "fallback"
