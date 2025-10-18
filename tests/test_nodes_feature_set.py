"""Tests for the expanded node ecosystem described in the roadmap."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from orcheo.graph.state import State
from orcheo.nodes.data_logic import (
    DataTransformNode,
    HttpRequestNode,
    IfElseNode,
    JsonProcessingNode,
    MergeNode,
    SetVariableNode,
    SwitchNode,
)
from orcheo.nodes.guardrails import GuardrailsNode
from orcheo.nodes.llm import (
    AnthropicChatNode,
    CustomAgentNode,
    OpenAIChatNode,
    TextProcessingNode,
)
from orcheo.nodes.triggers import (
    CronTriggerNode,
    HttpPollingTriggerNode,
    ManualTriggerNode,
    WebhookTriggerNode,
)
from orcheo.nodes.utility import DebugNode, DelayNode, SubWorkflowNode


@pytest.mark.asyncio
async def test_webhook_trigger_verifies_signature() -> None:
    state: State = {
        "inputs": {
            "body": {"message": "hello"},
            "headers": {"x-orcheo-signature": "secret"},
        }
    }
    node = WebhookTriggerNode(name="webhook", secret="secret")
    result = await node.run(state, config={})
    assert result["verified"] is True


@pytest.mark.asyncio
async def test_cron_trigger_returns_next_dispatch() -> None:
    node = CronTriggerNode(name="cron", schedule="*/5 * * * *")
    result = await node.run({}, config={})
    dispatch = datetime.fromisoformat(result["next_dispatch_at"])
    assert dispatch.tzinfo == UTC


@pytest.mark.asyncio
async def test_manual_trigger_records_actor() -> None:
    node = ManualTriggerNode(name="manual", actor="qa")
    result = await node.run({}, config={})
    assert result["triggered_by"] == "qa"


@pytest.mark.asyncio
async def test_http_polling_trigger_uses_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)

    class DummyAsyncClient(httpx.AsyncClient):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("orcheo.nodes.triggers.httpx.AsyncClient", DummyAsyncClient)
    node = HttpPollingTriggerNode(name="poll", url="https://example.com")
    result = await node.run({}, config={})
    assert result["status_code"] == 200
    assert result["body"] == {"status": "ok"}


@pytest.mark.asyncio
async def test_http_request_node(monkeypatch: pytest.MonkeyPatch) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"echo": request.url.path})

    transport = httpx.MockTransport(handler)

    class DummyAsyncClient(httpx.AsyncClient):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("orcheo.nodes.data_logic.httpx.AsyncClient", DummyAsyncClient)
    node = HttpRequestNode(
        name="request", url="https://api.test.local/resource", method="POST"
    )
    result = await node.run({}, config={})
    assert result["status_code"] == 201
    assert result["body"] == {"echo": "/resource"}


@pytest.mark.asyncio
async def test_data_logic_nodes() -> None:
    state: State = {
        "results": {
            "input": "Hello World",
            "flag": True,
            "left": {"a": 1},
            "right": {"b": 2},
        }
    }
    transform = await DataTransformNode(name="transform", operation="uppercase").run(
        state, {}
    )
    assert transform == "HELLO WORLD"

    extracted = await JsonProcessingNode(name="extract", path="left.a").run(state, {})
    assert extracted == 1

    branch = await IfElseNode(
        name="branch", key="flag", when_true="A", when_false="B"
    ).run(state, {})
    assert branch["branch"] == "A"

    switch = await SwitchNode(name="switch", key="flag", cases={"True": "allowed"}).run(
        state, {}
    )
    assert switch["branch"] == "allowed"

    merged = await MergeNode(name="merge", left_key="left", right_key="right").run(
        state, {}
    )
    assert merged == {"a": 1, "b": 2}

    set_node = await SetVariableNode(name="set", value=42).run(state, {})
    assert set_node == {"set": 42}


@pytest.mark.asyncio
async def test_guardrails_and_utility_nodes() -> None:
    guard = await GuardrailsNode(
        name="guard",
        metrics={"latency": 2.0, "toxicity": 0.01},
        thresholds={"latency": 3.0, "toxicity": 0.1},
    ).run({}, {})
    assert guard["compliant"] is True

    debug = await DebugNode(name="debug", message="check").run(
        {"inputs": {"foo": "bar"}, "results": {"x": 1}}, {}
    )
    assert debug["snapshot"]["results"]["x"] == 1

    delay = await DelayNode(name="delay", seconds=0).run({}, {})
    assert delay["delayed_for"] == 0

    sub_workflow = await SubWorkflowNode(name="sub", steps=["a", "b"]).run(
        {}, {"run_id": "123"}
    )
    assert sub_workflow["sub_workflow"] == "sub"


@pytest.mark.asyncio
async def test_llm_nodes_enforce_guardrails() -> None:
    state: State = {"messages": [{"role": "user", "content": "Summarize this meeting"}]}

    openai = await OpenAIChatNode(name="openai").run(state, {})
    assert "OpenAI" in openai["messages"][0]["content"]

    anthropic = await AnthropicChatNode(name="anthropic").run(state, {})
    assert "Insight" in anthropic["messages"][0]["content"]

    agent = await CustomAgentNode(
        name="agent", tools=["search"], instructions="Report back"
    ).run(state, {})
    assert "search" in agent["messages"][0]["content"]

    text = await TextProcessingNode(name="processor", operation="word_count").run(
        state, {}
    )
    assert text["word_count"] >= 2

    slow_node = OpenAIChatNode(name="slow", max_latency_seconds=0.0)
    with pytest.raises(TimeoutError):
        await slow_node.run(state, {})
