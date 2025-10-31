"""Tests covering data nodes."""

from __future__ import annotations
import json
from datetime import timedelta
from typing import Any
import httpx
import pytest
import respx
from httpx import Response
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes import data as data_module
from orcheo.nodes.data import (
    DataTransformNode,
    FieldTransform,
    HttpRequestNode,
    JsonProcessingNode,
    MergeNode,
)


@pytest.mark.asyncio
async def test_http_request_node_returns_response_metadata() -> None:
    """HttpRequestNode should surface response details."""

    state = State({"results": {}})
    node = HttpRequestNode(
        name="http",
        method="GET",
        url="https://example.com/api",
    )

    with respx.mock(base_url="https://example.com") as router:
        router.get("/api").respond(200, json={"status": "ok"})
        payload = (await node(state, RunnableConfig()))["results"]["http"]

    assert payload["status_code"] == 200
    assert payload["json"] == {"status": "ok"}
    assert payload["url"].startswith("https://example.com/api")


@pytest.mark.asyncio
async def test_http_request_node_raises_for_http_errors() -> None:
    """HttpRequestNode should propagate HTTP errors when configured to do so."""

    state = State({"results": {}})
    node = HttpRequestNode(
        name="http",
        method="GET",
        url="https://example.com/not-found",
        raise_for_status=True,
    )

    with respx.mock(base_url="https://example.com") as router:
        router.get("/not-found").mock(
            return_value=Response(404, json={"error": "nope"})
        )
        with pytest.raises(httpx.HTTPStatusError):
            await node(state, RunnableConfig())


@pytest.mark.asyncio
async def test_http_request_node_handles_non_json_response() -> None:
    """HttpRequestNode should gracefully handle plain text responses."""

    state = State({"results": {}})
    node = HttpRequestNode(
        name="http",
        method="POST",
        url="https://example.com/api",
        content="payload",
    )

    with respx.mock(base_url="https://example.com") as router:
        router.post("/api").mock(
            return_value=Response(
                200,
                text="ok",
                extensions={"elapsed": timedelta(seconds=0.5)},
            )
        )
        payload = (await node(state, RunnableConfig()))["results"]["http"]

    assert payload["json"] is None
    assert payload["elapsed"] is not None and payload["elapsed"] >= 0
    assert payload["content"] == "ok"


@pytest.mark.asyncio
async def test_http_request_node_sends_json_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HttpRequestNode should include JSON payloads when provided."""

    captured: dict[str, Any] = {}

    async def fake_request(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        captured["method"] = method
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        return httpx.Response(
            201,
            json={"ok": True},
            extensions={"elapsed": timedelta(seconds=1)},
        )

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    node = HttpRequestNode(
        name="http",
        method="PUT",
        url="https://example.com/api",
        json_body={"alpha": 1},
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["http"]

    assert captured == {
        "method": "PUT",
        "url": "https://example.com/api",
        "json": {"alpha": 1},
    }
    assert payload["json"] == {"ok": True}
    assert payload["elapsed"] == 1.0


@pytest.mark.asyncio
async def test_http_request_node_sends_form_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HttpRequestNode should include form data payloads when provided."""

    captured: dict[str, Any] = {}

    async def fake_request(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        captured["method"] = method
        captured["url"] = url
        captured["data"] = kwargs.get("data")
        return httpx.Response(
            200,
            json={"success": True},
        )

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    node = HttpRequestNode(
        name="http",
        method="POST",
        url="https://example.com/form",
        data={"field1": "value1", "field2": "value2"},
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["http"]

    assert captured["data"] == {"field1": "value1", "field2": "value2"}
    assert payload["json"] == {"success": True}


@pytest.mark.asyncio
async def test_http_request_node_handles_elapsed_from_response_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HttpRequestNode should handle elapsed time from response.elapsed attribute."""

    class MockResponse(httpx.Response):
        """Mock response with elapsed attribute."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._elapsed = timedelta(seconds=2.5)

        @property
        def elapsed(self) -> timedelta:
            return self._elapsed

    async def fake_request(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        return MockResponse(200, json={"ok": True})

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    node = HttpRequestNode(
        name="http",
        method="GET",
        url="https://example.com/api",
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["http"]

    assert payload["elapsed"] == 2.5


def test_split_path_raises_for_empty_values() -> None:
    """_split_path should raise an error when no segments remain."""

    with pytest.raises(ValueError):
        data_module._split_path("...")


def test_extract_value_handles_sequence_indexes() -> None:
    """_extract_value should support sequence lookups and invalid branches."""

    found, value = data_module._extract_value(["a", "b", "c"], "1")
    assert found is True and value == "b"

    found, value = data_module._extract_value(["a"], "invalid")
    assert found is False and value is None

    found, value = data_module._extract_value(["only"], "10")
    assert found is False and value is None

    found, value = data_module._extract_value(123, "field")
    assert found is False and value is None


def test_assign_path_constructs_nested_structure() -> None:
    """_assign_path should build nested dictionaries as needed."""

    target: dict[str, Any] = {}
    data_module._assign_path(target, "user.profile.name", "Ada")
    assert target == {"user": {"profile": {"name": "Ada"}}}


def test_deep_merge_combines_nested_mappings() -> None:
    """_deep_merge should merge nested dictionaries recursively."""

    base = {"alpha": 1, "nested": {"x": 1}}
    incoming = {"beta": 2, "nested": {"y": 2}}
    merged = data_module._deep_merge(base, incoming)
    assert merged == {"alpha": 1, "beta": 2, "nested": {"x": 1, "y": 2}}


@pytest.mark.asyncio
async def test_json_processing_node_extracts_values() -> None:
    """JsonProcessingNode should extract nested values."""

    state = State({"results": {}})
    data = json.dumps({"person": {"name": "Ada", "languages": ["python", "c"]}})
    node = JsonProcessingNode(
        name="json",
        operation="extract",
        input_data=data,
        path="person.languages.0",
    )

    payload = (await node(state, RunnableConfig()))["results"]["json"]
    assert payload["result"] == "python"
    assert payload["found"] is True


@pytest.mark.asyncio
async def test_json_processing_node_handles_missing_path() -> None:
    """Missing paths should emit default values."""

    state = State({"results": {}})
    node = JsonProcessingNode(
        name="json",
        operation="extract",
        input_data={"alpha": 1},
        path="beta",
        default="fallback",
    )

    payload = (await node(state, RunnableConfig()))["results"]["json"]
    assert payload["result"] == "fallback"
    assert payload["found"] is False


@pytest.mark.asyncio
async def test_json_processing_node_stringifies_payloads() -> None:
    """Stringify mode should serialise objects with indentation."""

    state = State({"results": {}})
    node = JsonProcessingNode(
        name="json",
        operation="stringify",
        input_data={"alpha": 1},
        indent=0,
        ensure_ascii=True,
    )

    payload = (await node(state, RunnableConfig()))["results"]["json"]
    assert json.loads(payload["result"]) == {"alpha": 1}


@pytest.mark.asyncio
async def test_json_processing_node_parses_inputs() -> None:
    """Parse mode should handle string and native inputs."""

    state = State({"results": {}})
    node_text = JsonProcessingNode(name="json", operation="parse", input_data="1")
    node_dict = JsonProcessingNode(
        name="json", operation="parse", input_data={"k": "v"}
    )

    text_payload = (await node_text(state, RunnableConfig()))["results"]["json"]
    dict_payload = (await node_dict(state, RunnableConfig()))["results"]["json"]

    assert text_payload["result"] == 1
    assert dict_payload["result"] == {"k": "v"}


@pytest.mark.asyncio
async def test_json_processing_node_requires_path() -> None:
    """Extract mode without a path should raise an error."""

    state = State({"results": {}})
    node = JsonProcessingNode(name="json", operation="extract", input_data={})

    with pytest.raises(ValueError):
        await node(state, RunnableConfig())


@pytest.mark.asyncio
async def test_json_processing_node_rejects_unknown_operation() -> None:
    """An unsupported operation should raise an error."""

    node = JsonProcessingNode(name="json", operation="parse", input_data={})
    node.operation = "invalid"  # type: ignore[assignment]
    state = State({"results": {}})

    with pytest.raises(ValueError):
        await node(state, RunnableConfig())


@pytest.mark.asyncio
async def test_data_transform_node_applies_mappings() -> None:
    """DataTransformNode should remap fields and apply transforms."""

    state = State({"results": {}})
    node = DataTransformNode(
        name="transform",
        input_data={"user": {"name": "Ada", "age": "37"}},
        transforms=[
            FieldTransform(
                source="user.name",
                target="profile.full_name",
                transform="upper",
            ),
            FieldTransform(
                source="user.age",
                target="profile.age",
                transform="int",
            ),
        ],
    )

    payload = (await node(state, RunnableConfig()))["results"]["transform"]
    assert payload["result"] == {"profile": {"full_name": "ADA", "age": 37}}


@pytest.mark.asyncio
async def test_data_transform_node_supports_conversions() -> None:
    """DataTransformNode should handle conversion transforms."""

    state = State({"results": {}})
    node = DataTransformNode(
        name="convert",
        input_data={"value": "5", "text": "Ada", "items": [1, 2]},
        transforms=[
            FieldTransform(source="value", target="numeric.int", transform="int"),
            FieldTransform(source="value", target="numeric.float", transform="float"),
            FieldTransform(source="value", target="numeric.bool", transform="bool"),
            FieldTransform(source="text", target="text.lower", transform="lower"),
            FieldTransform(source="text", target="text.upper", transform="upper"),
            FieldTransform(source="text", target="text.title", transform="title"),
            FieldTransform(source="items", target="counts.length", transform="length"),
            FieldTransform(source=None, target="defaults.message", default="hi"),
        ],
    )

    payload = (await node(state, RunnableConfig()))["results"]["convert"]
    assert payload["result"] == {
        "numeric": {"int": 5, "float": 5.0, "bool": True},
        "text": {"lower": "ada", "upper": "ADA", "title": "Ada"},
        "counts": {"length": 2},
        "defaults": {"message": "hi"},
    }


@pytest.mark.asyncio
async def test_data_transform_node_skips_missing_values() -> None:
    """Missing fields should be skipped when configured."""

    state = State({"results": {}})
    node = DataTransformNode(
        name="skip",
        input_data={},
        transforms=[
            FieldTransform(
                source="missing",
                target="result.value",
                when_missing="skip",
            )
        ],
    )

    payload = (await node(state, RunnableConfig()))["results"]["skip"]
    assert payload["result"] == {}


@pytest.mark.asyncio
async def test_data_transform_node_uses_default_for_missing_values() -> None:
    """Missing fields should use default when when_missing is 'default'."""

    state = State({"results": {}})
    node = DataTransformNode(
        name="defaults",
        input_data={"existing": "value"},
        transforms=[
            FieldTransform(
                source="missing_field",
                target="result.value",
                when_missing="default",
                default="default_value",
            )
        ],
    )

    payload = (await node(state, RunnableConfig()))["results"]["defaults"]
    assert payload["result"] == {"result": {"value": "default_value"}}


def test_apply_transform_handles_unknown_key() -> None:
    """_apply_transform should return original values for unknown transforms."""

    assert data_module._apply_transform("value", "unknown") == "value"


def test_transform_length_handles_various_inputs() -> None:
    """_transform_length should support mappings and fallback to zero."""

    assert data_module._transform_length({"key": "value"}) == 1
    assert data_module._transform_length(object()) == 0


def test_transform_string_handles_none() -> None:
    """_transform_string should convert None to empty string."""

    assert data_module._transform_string(None) == ""
    assert data_module._transform_string("test") == "test"
    assert data_module._transform_string(123) == "123"


@pytest.mark.asyncio
async def test_merge_node_deep_merges_mappings() -> None:
    """MergeNode should merge dictionaries recursively by default."""

    state = State({"results": {}})
    node = MergeNode(
        name="merge",
        items=[
            {"a": 1, "nested": {"x": 1}},
            {"b": 2, "nested": {"y": 2}},
        ],
    )

    payload = (await node(state, RunnableConfig()))["results"]["merge"]
    assert payload["result"] == {"a": 1, "b": 2, "nested": {"x": 1, "y": 2}}


@pytest.mark.asyncio
async def test_merge_node_concatenates_lists_with_deduplication() -> None:
    """MergeNode should deduplicate values when requested."""

    state = State({"results": {}})
    node = MergeNode(
        name="merge",
        items=[["alpha", "beta"], ["beta", "gamma"]],
        mode="list",
        deduplicate=True,
    )

    payload = (await node(state, RunnableConfig()))["results"]["merge"]
    assert payload["result"] == ["alpha", "beta", "gamma"]


@pytest.mark.asyncio
async def test_merge_node_supports_shallow_updates() -> None:
    """MergeNode should respect the shallow update flag."""

    state = State({"results": {}})
    node = MergeNode(
        name="merge",
        items=[{"nested": {"x": 1}}, {"nested": {"y": 2}}],
        deep=False,
    )

    payload = (await node(state, RunnableConfig()))["results"]["merge"]
    assert payload["result"] == {"nested": {"y": 2}}


@pytest.mark.asyncio
async def test_merge_node_validates_items_for_lists() -> None:
    """MergeNode should raise when list mode receives invalid items."""

    state = State({"results": {}})
    node = MergeNode(name="merge", items=[{"a": 1}], mode="list")

    with pytest.raises(ValueError):
        await node(state, RunnableConfig())


@pytest.mark.asyncio
async def test_merge_node_infers_mode_errors() -> None:
    """MergeNode should error when auto mode cannot infer a strategy."""

    node = MergeNode(name="merge", items=["string"], mode="auto")
    state = State({"results": {}})

    with pytest.raises(ValueError):
        await node(state, RunnableConfig())


@pytest.mark.asyncio
async def test_merge_node_auto_detects_list_mode() -> None:
    """MergeNode should infer list mode for sequence inputs."""

    state = State({"results": {}})
    node = MergeNode(name="merge", items=[[1, 2], [3]], mode="auto")
    payload = (await node(state, RunnableConfig()))["results"]["merge"]
    assert payload["result"] == [1, 2, 3]


@pytest.mark.asyncio
async def test_merge_node_validates_dict_items() -> None:
    """MergeNode should raise when dictionary merge receives invalid items."""

    state = State({"results": {}})
    node = MergeNode(name="merge", items=[{"a": 1}, [1, 2]], mode="dict")

    with pytest.raises(ValueError):
        await node(state, RunnableConfig())


@pytest.mark.asyncio
async def test_merge_node_returns_empty_for_no_items() -> None:
    """MergeNode should return an empty structure when nothing is provided."""

    state = State({"results": {}})
    node = MergeNode(name="merge", items=[], mode="dict")
    payload = (await node(state, RunnableConfig()))["results"]["merge"]
    assert payload["result"] == {}

    list_node = MergeNode(name="merge", items=[], mode="list")
    payload = (await list_node(state, RunnableConfig()))["results"]["merge"]
    assert payload["result"] == []
