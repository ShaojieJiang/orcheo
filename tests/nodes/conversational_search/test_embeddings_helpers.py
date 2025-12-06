"""Tests for embedding registration helpers."""

from __future__ import annotations
import inspect
from typing import Any
import pytest
from langchain_core.embeddings import Embeddings
from orcheo.nodes.conversational_search.embeddings import (
    register_langchain_embedding,
    register_pinecone_bm25_embedding,
    register_pinecone_splade_embedding,
)
from orcheo.nodes.conversational_search.ingestion import resolve_embedding_method


class _FakeEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text))] for text in texts]

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
