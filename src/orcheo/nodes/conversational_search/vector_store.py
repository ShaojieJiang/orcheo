"""Vector store abstractions used by conversational search nodes."""

from __future__ import annotations
import inspect
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from orcheo.nodes.conversational_search.models import SearchResult, VectorRecord


class BaseVectorStore(ABC, BaseModel):
    """Abstract interface for vector store adapters."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @abstractmethod
    async def upsert(self, records: Iterable[VectorRecord]) -> None:
        """Persist ``records`` into the backing vector store."""

    @abstractmethod
    async def query(
        self,
        vector: list[float],
        top_k: int = 10,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Return top ``top_k`` matches with optional metadata filtering."""


class InMemoryVectorStore(BaseVectorStore):
    """Simple in-memory vector store useful for testing and local dev."""

    records: dict[str, VectorRecord] = Field(default_factory=dict)

    async def upsert(self, records: Iterable[VectorRecord]) -> None:
        """Store ``records`` in the in-memory dictionary."""
        for record in records:
            self.records[record.id] = record

    async def query(
        self,
        vector: list[float],
        top_k: int = 10,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Return cosine-similar matches from the in-memory store."""
        if not self.records:
            return []
        if not vector:
            msg = "Query vector cannot be empty"
            raise ValueError(msg)

        filtered = list(self.records.values())
        if filter_metadata:
            filtered = [
                record
                for record in filtered
                if self._metadata_matches(record.metadata, filter_metadata)
            ]
        if not filtered:
            return []

        scored = [
            (
                record,
                self._cosine_similarity(vector, record.values),
            )
            for record in filtered
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        results: list[SearchResult] = []
        for record, score in scored[:top_k]:
            results.append(
                SearchResult(
                    id=record.id,
                    content=record.text,
                    metadata=record.metadata,
                    score=score,
                    source="vector",
                    sources=["vector"],
                )
            )
        return results

    @staticmethod
    def _metadata_matches(metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
        return all(metadata.get(key) == value for key, value in filters.items())

    @staticmethod
    def _cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
        if len(vector_a) != len(vector_b):
            msg = "Query vector dimension does not match stored vector"
            raise ValueError(msg)
        dot = sum(a * b for a, b in zip(vector_a, vector_b, strict=True))
        norm_a = sum(a * a for a in vector_a) ** 0.5
        norm_b = sum(b * b for b in vector_b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def list(self) -> list[VectorRecord]:  # pragma: no cover - helper
        """Return a copy of stored records for inspection."""
        return list(self.records.values())


class PineconeVectorStore(BaseVectorStore):
    """Lightweight Pinecone adapter that defers client loading until use."""

    index_name: str
    namespace: str | None = None
    client: Any | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def upsert(self, records: Iterable[VectorRecord]) -> None:
        """Upsert ``records`` into Pinecone with dependency guards."""
        client = self._resolve_client()
        index = self._resolve_index(client)
        payload = [
            {
                "id": record.id,
                "values": record.values,
                "metadata": record.metadata | {"text": record.text},
            }
            for record in records
        ]
        result = index.upsert(vectors=payload, namespace=self.namespace)
        if inspect.iscoroutine(result):
            await result

    async def query(
        self,
        vector: list[float],
        top_k: int = 10,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Query Pinecone for ``top_k`` matches using the provided vector."""
        client = self._resolve_client()
        index = self._resolve_index(client)
        response = index.query(
            namespace=self.namespace,
            top_k=top_k,
            vector=vector,
            filter=filter_metadata or None,
            include_metadata=True,
            include_values=False,
        )
        if inspect.iscoroutine(response):
            response = await response
        matches = getattr(response, "matches", None)
        if matches is None:
            if isinstance(response, dict):
                matches = response.get("matches", [])
            else:
                matches = getattr(response, "get", lambda *_: [])("matches", [])
        matches = matches or []
        results: list[SearchResult] = []
        for match in matches:
            metadata = self._get_match_field(match, "metadata", {}) or {}
            if hasattr(metadata, "model_dump"):
                metadata = metadata.model_dump()
            elif not isinstance(metadata, dict):
                metadata = dict(metadata) if hasattr(metadata, "items") else {}
            text = metadata.get("text", "")
            results.append(
                SearchResult(
                    id=str(self._get_match_field(match, "id")),
                    content=text,
                    metadata=metadata,
                    score=float(self._get_match_field(match, "score", 0.0)),
                    source="vector",
                    sources=["vector"],
                )
            )
        return results

    @staticmethod
    def _get_match_field(match: Any, field: str, default: Any = None) -> Any:
        if hasattr(match, field):
            return getattr(match, field)
        if isinstance(match, dict):
            return match.get(field, default)
        getter = getattr(match, "get", None)
        if callable(getter):
            return getter(field, default)
        return default

    def _resolve_client(self) -> Any:
        if self.client is not None:
            return self.client
        try:
            from pinecone import Pinecone  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency guard
            msg = (
                "PineconeVectorStore requires the 'pinecone-client' dependency. "
                "Install it or provide a pre-configured client."
            )
            raise ImportError(msg) from exc
        self.client = Pinecone()
        return self.client

    def _resolve_index(self, client: Any) -> Any:
        try:
            return client.Index(self.index_name)
        except Exception as exc:  # pragma: no cover - runtime guard
            msg = f"Unable to open Pinecone index '{self.index_name}': {exc!s}"
            raise RuntimeError(msg) from exc
