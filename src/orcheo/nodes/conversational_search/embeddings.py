"""Helper utilities for registering conversational search embeddings."""

from __future__ import annotations
import inspect
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from langchain_core.embeddings import Embeddings
from orcheo.nodes.conversational_search.ingestion import (
    EmbeddingMethod,
    EmbeddingVector,
    register_embedding_method,
)
from orcheo.nodes.conversational_search.models import SparseValues


if TYPE_CHECKING:  # pragma: no cover - used for typing only
    from pinecone_text.sparse import BM25Encoder, SpladeEncoder


BM25Mode = Literal["documents", "queries"]
SparseEncoderFactory = Callable[[], Any]


def register_langchain_embedding(
    name: str,
    embedding: Embeddings | Callable[[], Embeddings],
) -> EmbeddingMethod:
    """Register a LangChain embedding instance or factory."""

    def _resolve() -> Embeddings:
        instance = embedding() if callable(embedding) else embedding
        if not isinstance(instance, Embeddings):
            msg = "LangChain embedding factories must return Embeddings instances"
            raise TypeError(msg)
        return instance

    async def _embed(texts: list[str]) -> list[list[float]]:
        instance = _resolve()
        result = instance.embed_documents(texts)
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, list) or not all(
            isinstance(row, list) for row in result
        ):
            msg = "LangChain embeddings must return List[List[float]]"
            raise ValueError(msg)
        return result

    return register_embedding_method(name, _embed)


def register_pinecone_bm25_embedding(
    name: str,
    *,
    mode: BM25Mode = "documents",
    encoder: BM25Encoder | SparseEncoderFactory | None = None,
    encoder_state_path: str | Path | None = None,
    fit_on_call: bool | None = None,
) -> EmbeddingMethod:
    """Register a Pinecone BM25 encoder as an embedding method."""
    _validate_sparse_mode(mode)
    _validate_bm25_configuration(mode, encoder, encoder_state_path)
    builder = _bm25_encoder_builder(encoder, encoder_state_path)
    should_fit = (
        encoder_state_path is None and mode == "documents"
        if fit_on_call is None
        else fit_on_call
    )
    embed_fn = _bm25_embed_function(builder, mode, should_fit)
    return register_embedding_method(name, embed_fn)


def register_pinecone_splade_embedding(
    name: str,
    *,
    encoder: SpladeEncoder | SparseEncoderFactory | None = None,
    mode: BM25Mode = "documents",
    max_seq_length: int = 256,
    device: str | None = None,
) -> EmbeddingMethod:
    """Register a Pinecone SPLADE encoder as an embedding method."""
    _validate_sparse_mode(mode)
    resolver = _splade_encoder_resolver(encoder, max_seq_length, device)
    embed_fn = _splade_embed_function(resolver, mode)
    return register_embedding_method(name, embed_fn)


def _validate_sparse_mode(mode: str) -> None:
    if mode not in {"documents", "queries"}:
        msg = "mode must be either 'documents' or 'queries'"
        raise ValueError(msg)


def _validate_bm25_configuration(
    mode: BM25Mode,
    encoder: BM25Encoder | SparseEncoderFactory | None,
    encoder_state_path: str | Path | None,
) -> None:
    if mode != "queries":
        return
    if encoder is not None or callable(encoder):
        return
    if encoder_state_path is not None:
        return
    msg = "Query mode requires a pre-fitted encoder or encoder_state_path"
    raise ValueError(msg)


def _bm25_encoder_builder(
    encoder: BM25Encoder | SparseEncoderFactory | None,
    encoder_state_path: str | Path | None,
) -> Callable[[], BM25Encoder]:
    from pinecone_text.sparse import BM25Encoder

    def _builder() -> BM25Encoder:
        if callable(encoder):
            return encoder()
        if encoder is not None:
            return encoder
        if encoder_state_path is not None:
            path = Path(encoder_state_path)
            if not path.exists():
                msg = f"Encoder state path does not exist: {encoder_state_path}"
                raise FileNotFoundError(msg)
            return BM25Encoder.load(str(path))
        return BM25Encoder()

    return _builder


def _bm25_embed_function(
    encoder_builder: Callable[[], BM25Encoder],
    mode: BM25Mode,
    fit_on_call: bool,
) -> EmbeddingMethod:
    def _bm25_embed(texts: list[str]) -> list[EmbeddingVector]:
        encoder_instance = encoder_builder()
        if fit_on_call:  # pragma: no branch
            encoder_instance.fit(texts)
        payload = (
            encoder_instance.encode_documents(texts)
            if mode == "documents"
            else encoder_instance.encode_queries(texts)
        )
        return [
            EmbeddingVector(values=[], sparse_values=sparse)
            for sparse in _encode_sparse_vectors(payload)
        ]

    return _bm25_embed


def _encode_sparse_vectors(payload: Any) -> list[SparseValues]:
    vectors = payload if isinstance(payload, list) else [payload]
    sparse_vectors: list[SparseValues] = []
    for entry in vectors:
        if isinstance(entry, SparseValues):
            sparse_vectors.append(entry)
        elif isinstance(entry, dict):
            sparse_vectors.append(SparseValues.model_validate(entry))
        else:
            msg = "Sparse encoder returned an invalid payload"
            raise ValueError(msg)
    return sparse_vectors


def _splade_encoder_resolver(
    encoder: SpladeEncoder | SparseEncoderFactory | None,
    max_seq_length: int,
    device: str | None,
) -> Callable[[], SpladeEncoder]:
    def _resolver() -> SpladeEncoder:
        if callable(encoder):
            return encoder()
        if encoder is not None:
            return encoder
        try:
            from pinecone_text.sparse import SpladeEncoder
        except ImportError as exc:  # pragma: no cover - dependency guard
            msg = (
                "register_pinecone_splade_embedding requires the 'pinecone-text' "
                "package with the 'splade' extra installed."
            )
            raise ImportError(msg) from exc
        return SpladeEncoder(max_seq_length=max_seq_length, device=device)

    return _resolver


def _splade_embed_function(
    encoder_resolver: Callable[[], SpladeEncoder],
    mode: BM25Mode,
) -> EmbeddingMethod:
    def _splade_embed(texts: list[str]) -> list[EmbeddingVector]:
        encoder_instance = encoder_resolver()
        payload = (
            encoder_instance.encode_documents(texts)
            if mode == "documents"
            else encoder_instance.encode_queries(texts)
        )
        return [
            EmbeddingVector(values=[], sparse_values=sparse)
            for sparse in _encode_sparse_vectors(payload)
        ]

    return _splade_embed
