from __future__ import annotations

import httpx
import pytest

from orcheo.graph.state import State
from orcheo.nodes.data import (
    DataTransform,
    HttpRequest,
    JsonExtractor,
    TransformMapping,
)


@pytest.mark.asyncio()
async def test_http_request_node(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"ok": True})
    )

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            self._client = httpx.AsyncClient(transport=transport)

        async def __aenter__(self) -> "DummyAsyncClient":
            return self

        async def __aexit__(self, *exc_info) -> None:
            await self._client.aclose()

        async def request(self, *args, **kwargs) -> httpx.Response:
            return await self._client.request(*args, **kwargs)

    monkeypatch.setattr("orcheo.nodes.data.httpx.AsyncClient", DummyAsyncClient)

    node = HttpRequest(name="http", url="https://example.com/api")
    state = State({"results": {}})
    output = await node(state, None)
    assert output["results"]["http"]["body"] == {"ok": True}


@pytest.mark.asyncio()
async def test_json_extractor_node() -> None:
    state = State({"results": {"payload": {"nested": {"value": 42}}}})
    node = JsonExtractor(name="extract", path=["payload", "nested", "value"])
    output = await node(state, None)
    assert output["results"]["extract"] == 42


@pytest.mark.asyncio()
async def test_data_transform_node() -> None:
    state = State({"results": {"source": {"a": 2, "b": 3}}})
    node = DataTransform(
        name="transform",
        source_key="source",
        mappings=[
            TransformMapping(target="sum", expression="data['a'] + data['b']"),
            TransformMapping(target="product", expression="data['a'] * data['b']"),
        ],
    )
    output = await node(state, None)
    assert output["results"]["transform"] == {"sum": 5, "product": 6}
