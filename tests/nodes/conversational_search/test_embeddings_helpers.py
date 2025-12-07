"""Tests for embedding registration helpers."""

from __future__ import annotations
import inspect
from pathlib import Path
from typing import Any
import pytest
from langchain_core.embeddings import Embeddings
from orcheo.nodes.conversational_search.embeddings import (
    _bm25_encoder_builder,
    _encode_sparse_vectors,
    _splade_encoder_resolver,
    _validate_bm25_configuration,
    _validate_sparse_mode,
    register_langchain_embedding,
    register_pinecone_bm25_embedding,
    register_pinecone_splade_embedding,
)
from orcheo.nodes.conversational_search.ingestion import resolve_embedding_method
from orcheo.nodes.conversational_search.models import SparseValues


class _FakeEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text))] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text))]


class _AsyncEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> Any:
        async def _inner() -> list[list[float]]:
            return [[float(len(text))] for text in texts]

        return _inner()

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text))]


class _InvalidStructureEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[str]:
        return ["invalid"] * len(texts)

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text))]


@pytest.mark.asyncio
async def test_register_langchain_embedding_supports_factory() -> None:
    method_name = "langchain-factory"
    register_langchain_embedding(method_name, lambda: _FakeEmbeddings())
    embedder = resolve_embedding_method(method_name)

    result = await embedder(["hello", "world"])
    assert result == [[5.0], [5.0]]


@pytest.mark.asyncio
async def test_register_langchain_embedding_awaits_async_result() -> None:
    method_name = "langchain-awaitable"
    register_langchain_embedding(method_name, _AsyncEmbeddings())
    embedder = resolve_embedding_method(method_name)

    result = await embedder(["short", "longer"])
    assert result == [[5.0], [6.0]]


@pytest.mark.asyncio
async def test_register_langchain_embedding_rejects_non_embeddings_factory() -> None:
    method_name = "langchain-bad-factory"
    register_langchain_embedding(method_name, lambda: object())
    embedder = resolve_embedding_method(method_name)

    with pytest.raises(
        TypeError,
        match="LangChain embedding factories must return Embeddings instances",
    ):
        await embedder(["anything"])


@pytest.mark.asyncio
async def test_register_langchain_embedding_rejects_invalid_output() -> None:
    method_name = "langchain-invalid-output"
    register_langchain_embedding(method_name, _InvalidStructureEmbeddings())
    embedder = resolve_embedding_method(method_name)

    with pytest.raises(
        ValueError,
        match="LangChain embeddings must return List\\[List\\[float\\]\\]",
    ):
        await embedder(["bad"])


@pytest.mark.asyncio
async def test_register_pinecone_bm25_embedding_produces_sparse_vectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeBM25:
        instances: list[FakeBM25] = []

        def __init__(self) -> None:
            self.fit_calls: int = 0
            type(self).instances.append(self)

        def fit(self, texts: list[str]) -> None:
            self.fit_calls += 1

        def encode_documents(self, texts: list[str]) -> list[dict[str, Any]]:
            return [{"indices": [idx], "values": [1.0]} for idx, _ in enumerate(texts)]

        def encode_queries(self, texts: list[str]) -> list[dict[str, Any]]:
            return [{"indices": [0], "values": [0.5]} for _ in texts]

        @classmethod
        def load(cls, path: str) -> FakeBM25:  # pragma: no cover - not used here
            instance = cls()
            instance.loaded_path = path  # type: ignore[attr-defined]
            return instance

    import pinecone_text.sparse as pinecone_sparse

    monkeypatch.setattr(pinecone_sparse, "BM25Encoder", FakeBM25)
    method_name = "bm25-helpers"
    register_pinecone_bm25_embedding(method_name)
    embedder = resolve_embedding_method(method_name)

    result = embedder(["chunk-one"])
    if inspect.isawaitable(result):
        result = await result
    vectors = result
    assert len(vectors) == 1
    assert vectors[0].sparse_values is not None
    assert FakeBM25.instances[0].fit_calls == 1


def test_register_pinecone_bm25_embedding_requires_prefit_for_queries() -> None:
    with pytest.raises(ValueError, match="Query mode requires a pre-fitted encoder"):
        register_pinecone_bm25_embedding("bm25-query", mode="queries")


def test_validate_sparse_mode_rejects_invalid_mode() -> None:
    with pytest.raises(
        ValueError, match="mode must be either 'documents' or 'queries'"
    ):
        _validate_sparse_mode("invalid")


def test_validate_bm25_configuration_accepts_callable_encoder() -> None:
    _validate_bm25_configuration("queries", lambda: object(), None)


def test_validate_bm25_configuration_accepts_state_path() -> None:
    _validate_bm25_configuration("queries", None, "pretrained-state")


def test_bm25_encoder_builder_prefers_callable(monkeypatch: pytest.MonkeyPatch) -> None:
    import pinecone_text.sparse as pinecone_sparse

    class DummyBM25:
        pass

    monkeypatch.setattr(pinecone_sparse, "BM25Encoder", DummyBM25)

    sentinel = object()

    def factory() -> object:
        return sentinel

    builder = _bm25_encoder_builder(factory, None)
    assert builder() is sentinel


def test_bm25_encoder_builder_returns_encoder_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pinecone_text.sparse as pinecone_sparse

    class DummyBM25:
        pass

    monkeypatch.setattr(pinecone_sparse, "BM25Encoder", DummyBM25)
    encoder = object()

    builder = _bm25_encoder_builder(encoder, None)
    assert builder() is encoder


def test_bm25_encoder_builder_loads_state_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import pinecone_text.sparse as pinecone_sparse

    class DummyBM25:
        load_calls: list[str] = []

        def __init__(self) -> None:
            pass

        @classmethod
        def load(cls, path: str) -> DummyBM25:
            cls.load_calls.append(path)
            return cls()

    DummyBM25.load_calls = []
    monkeypatch.setattr(pinecone_sparse, "BM25Encoder", DummyBM25)
    state_path = tmp_path / "state.bin"
    state_path.write_text("state data")

    builder = _bm25_encoder_builder(None, state_path)
    instance = builder()

    assert isinstance(instance, DummyBM25)
    assert DummyBM25.load_calls == [str(state_path)]


def test_bm25_encoder_builder_missing_state_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import pinecone_text.sparse as pinecone_sparse

    class DummyBM25:
        pass

    monkeypatch.setattr(pinecone_sparse, "BM25Encoder", DummyBM25)
    missing_path = tmp_path / "missing.bin"
    builder = _bm25_encoder_builder(None, missing_path)

    with pytest.raises(FileNotFoundError, match="Encoder state path does not exist"):
        builder()


def test_encode_sparse_vectors_accepts_sparse_values_instance() -> None:
    sparse = SparseValues(indices=[0], values=[1.0])
    assert _encode_sparse_vectors(sparse) == [sparse]


def test_encode_sparse_vectors_accepts_dict_payload() -> None:
    payload = {"indices": [1], "values": [0.5]}
    assert _encode_sparse_vectors(payload) == [SparseValues(indices=[1], values=[0.5])]


def test_encode_sparse_vectors_rejects_invalid_payload() -> None:
    with pytest.raises(ValueError, match="Sparse encoder returned an invalid payload"):
        _encode_sparse_vectors("bad")


def test_splade_encoder_resolver_prefers_callable() -> None:
    sentinel = object()
    resolver = _splade_encoder_resolver(lambda: sentinel, 32, "cpu")
    assert resolver() is sentinel


def test_splade_encoder_resolver_prefers_instance() -> None:
    sentinel = object()
    resolver = _splade_encoder_resolver(sentinel, 32, "cpu")
    assert resolver() is sentinel


@pytest.mark.asyncio
async def test_register_pinecone_splade_embedding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSplade:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def encode_documents(self, texts: list[str]) -> list[dict[str, Any]]:
            return [{"indices": [idx], "values": [1.0]} for idx, _ in enumerate(texts)]

        def encode_queries(self, texts: list[str]) -> list[dict[str, Any]]:
            return [{"indices": [0], "values": [0.5]} for _ in texts]

    import pinecone_text.sparse as pinecone_sparse

    monkeypatch.setattr(pinecone_sparse, "SpladeEncoder", FakeSplade)
    method_name = "splade-helpers"
    register_pinecone_splade_embedding(method_name)
    embedder = resolve_embedding_method(method_name)

    result = embedder(["chunk-one", "chunk-two"])
    if inspect.isawaitable(result):
        result = await result
    vectors = result
    assert len(vectors) == 2
    assert all(vector.sparse_values is not None for vector in vectors)
