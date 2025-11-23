"""Unit tests for conversational search conversational search vector stores."""

import sys
import types
import pytest
from orcheo.nodes.conversational_search.models import VectorRecord
from orcheo.nodes.conversational_search.vector_store import PineconeVectorStore


class _DummyIndex:
    def __init__(self) -> None:
        self.calls: list[tuple[list[dict], str | None]] = []

    async def upsert(self, vectors: list[dict], namespace: str | None) -> None:
        self.calls.append((vectors, namespace))


class _DummyClient:
    def __init__(self, index: _DummyIndex) -> None:
        self._index = index

    def Index(self, name: str) -> _DummyIndex:  # noqa: N802
        return self._index


class _FailingClient:
    def Index(self, name: str) -> None:  # noqa: N802
        raise ValueError("boom")


class _SyncIndex:
    def __init__(self) -> None:
        self.calls: list[tuple[list[dict], str | None]] = []

    def upsert(self, vectors: list[dict], namespace: str | None) -> None:
        self.calls.append((vectors, namespace))


@pytest.mark.asyncio
async def test_pinecone_vector_store_upserts_with_provided_client() -> None:
    index = _DummyIndex()
    client = _DummyClient(index=index)
    store = PineconeVectorStore(
        index_name="pinecone-test", namespace="ns", client=client
    )
    record = VectorRecord(
        id="rec-1", values=[0.1], text="doc text", metadata={"foo": "bar"}
    )

    await store.upsert([record])

    payload, namespace = index.calls[0]
    assert namespace == "ns"
    assert payload[0]["metadata"]["foo"] == "bar"
    assert payload[0]["metadata"]["text"] == "doc text"


@pytest.mark.asyncio
async def test_pinecone_vector_store_handles_sync_upsert_result() -> None:
    index = _SyncIndex()
    client = _DummyClient(index=index)
    store = PineconeVectorStore(index_name="pinecone-sync", client=client)
    record = VectorRecord(
        id="rec-2", values=[0.2], text="second doc", metadata={"bar": "baz"}
    )

    await store.upsert([record])

    payload, namespace = index.calls[0]
    assert namespace is None
    assert payload[0]["metadata"]["bar"] == "baz"
    assert payload[0]["metadata"]["text"] == "second doc"


def test_pinecone_vector_store_resolves_client_from_dependency(monkeypatch) -> None:
    fake_module = types.ModuleType("pinecone")

    class FakePinecone:
        pass

    fake_module.Pinecone = FakePinecone
    monkeypatch.setitem(sys.modules, "pinecone", fake_module)

    store = PineconeVectorStore(index_name="pinecone-dependency")

    client = store._resolve_client()

    assert isinstance(client, FakePinecone)
    assert store.client is client


@pytest.mark.asyncio
async def test_pinecone_vector_store_raises_runtime_error_when_index_cannot_open() -> (
    None
):
    store = PineconeVectorStore(index_name="pinecone-bad", client=_FailingClient())

    with pytest.raises(
        RuntimeError, match="Unable to open Pinecone index 'pinecone-bad'"
    ):
        await store.upsert([])
