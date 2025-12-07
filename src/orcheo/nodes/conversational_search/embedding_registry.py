"""Global embedding registrations and identifiers for conversational search."""

from __future__ import annotations
from collections.abc import Callable
from typing import Final
from langchain_openai import OpenAIEmbeddings
from orcheo.nodes.conversational_search.embeddings import (
    register_langchain_embedding,
    register_pinecone_bm25_embedding,
)
from orcheo.nodes.conversational_search.ingestion import resolve_embedding_method


OPENAI_TEXT_EMBEDDING_3_SMALL: Final[str] = "embedding:openai:text-embedding-3-small"
PINECONE_BM25_DEFAULT: Final[str] = "embedding:pinecone:bm25-default"


def _safe_register(name: str, register_fn: Callable[[], object]) -> None:
    try:
        resolve_embedding_method(name)
    except ValueError:
        register_fn()


def _register_defaults() -> None:
    _safe_register(
        OPENAI_TEXT_EMBEDDING_3_SMALL,
        lambda: register_langchain_embedding(
            OPENAI_TEXT_EMBEDDING_3_SMALL,
            lambda: OpenAIEmbeddings(
                model="text-embedding-3-small",
                dimensions=512,
            ),
        ),
    )
    _safe_register(
        PINECONE_BM25_DEFAULT,
        lambda: register_pinecone_bm25_embedding(PINECONE_BM25_DEFAULT),
    )


_register_defaults()


__all__ = [
    "OPENAI_TEXT_EMBEDDING_3_SMALL",
    "PINECONE_BM25_DEFAULT",
]
