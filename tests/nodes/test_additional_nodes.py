from __future__ import annotations

from typing import Any

import pytest

from orcheo.graph.state import State
from orcheo.nodes.data_logic import (
    DataTransformNode,
    HttpRequestNode,
    IfElseNode,
    JsonProcessNode,
    MergeNode,
    SetVariableNode,
    SwitchNode,
)
from orcheo.nodes.guardrails import GuardrailsNode
from orcheo.nodes.storage import DiscordNode, EmailNode, PostgreSQLNode, SQLiteNode
from orcheo.nodes.triggers import (
    CronTriggerNode,
    HttpPollingTriggerNode,
    ManualTriggerNode,
    WebhookTriggerNode,
)
from orcheo.nodes.utilities import (
    DebugNode,
    DelayNode,
    JavaScriptCodeNode,
    SubWorkflowNode,
)


def _make_state(inputs: dict[str, Any], results: dict[str, Any]) -> State:
    return State(messages=[], inputs=inputs, results=results)


@pytest.mark.asyncio()
async def test_trigger_nodes_emit_configuration() -> None:
    state = _make_state({}, {})
    webhook = await WebhookTriggerNode(name="webhook", allowed_methods=["post"]).run(
        state, {}
    )
    assert webhook["type"] == "webhook"
    cron = await CronTriggerNode(name="cron", cron="0 * * * *").run(state, {})
    assert cron["cron"] == "0 * * * *"
    manual = await ManualTriggerNode(name="manual", batch_size=3).run(state, {})
    assert manual["batch_size"] == 3
    polling = await HttpPollingTriggerNode(
        name="poll", url="https://example.com", interval_seconds=10
    ).run(state, {})
    assert polling["interval_seconds"] == 30


@pytest.mark.asyncio()
async def test_data_logic_nodes_operate_on_state() -> None:
    state = _make_state(
        inputs={"user": {"id": 1}},
        results={"payload": {"message": "hi"}, "metrics": {"latency_ms": 20}},
    )
    http = await HttpRequestNode(name="req", url="https://api").run(state, {})
    assert http["method"] == "GET"
    json_value = await JsonProcessNode(name="extract", path="inputs.user.id").run(
        state, {}
    )
    assert json_value["value"] == 1
    transform = await DataTransformNode(
        name="map", mappings={"message": "results.payload.message"}
    ).run(state, {})
    assert transform["message"] == "hi"
    branch = await IfElseNode(
        name="cond", condition_path="results.metrics.latency_ms"
    ).run(state, {})
    assert branch["branch"] == "true"
    switch = await SwitchNode(
        name="switch",
        discriminator_path="results.payload.message",
        cases={"hi": "wave"},
    ).run(state, {})
    assert switch["branch"] == "wave"
    merged = await MergeNode(
        name="merge", sources=["results.payload", "inputs.user"]
    ).run(state, {})
    assert merged["message"] == "hi" and merged["id"] == 1
    set_var = await SetVariableNode(
        name="set", target="user_id", value_path="inputs.user.id"
    ).run(state, {})
    assert set_var["user_id"] == 1


@pytest.mark.asyncio()
async def test_storage_and_utility_nodes() -> None:
    state = _make_state({}, {})
    postgres = await PostgreSQLNode(
        name="pg", dsn="postgresql://localhost", sql="SELECT 1"
    ).run(state, {})
    assert postgres["sql"] == "SELECT 1"
    sqlite = await SQLiteNode(name="sqlite", path="/tmp/db.sqlite", sql="SELECT 1").run(
        state, {}
    )
    assert sqlite["path"].endswith("db.sqlite")
    email = await EmailNode(
        name="email", to=["user@example.com"], subject="Hello", body="Hi"
    ).run(state, {})
    assert email["to"] == ["user@example.com"]
    discord = await DiscordNode(
        name="discord", webhook_url="https://hooks", content="message"
    ).run(state, {})
    assert discord["content"] == "message"
    js = await JavaScriptCodeNode(name="js", source="return 1;").run(state, {})
    assert js["language"] == "javascript"
    delay = await DelayNode(name="delay", seconds=1.5).run(state, {})
    assert delay["seconds"] == pytest.approx(1.5)
    debug = await DebugNode(
        name="debug", message="inspect", sample_path="results.payload"
    ).run(_make_state({}, {"payload": {"key": "value"}}), {})
    assert debug["sample"] == {"key": "value"}
    sub = await SubWorkflowNode(
        name="sub", workflow_id="wf", version=2, inputs={"foo": "bar"}
    ).run(state, {})
    assert sub["workflow_id"] == "wf"


@pytest.mark.asyncio()
async def test_guardrails_node_evaluates_metrics() -> None:
    state = _make_state(
        inputs={},
        results={
            "metrics": {"latency_ms": 120, "tokens": 10},
            "payload": {"output": "ok"},
        },
    )
    guard = await GuardrailsNode(
        name="guard", max_latency_ms=100, max_tokens=5, required_fields=["output"]
    ).run(state, {})
    assert not guard["passed"]
    assert not guard["latency_ok"]
    assert not guard["token_budget_ok"]
