"""Vector store abstractions used by conversational search nodes."""

from __future__ import annotations
import inspect
import math
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
    async def search(
        self,
        query_vector: list[float],
        top_k: int,
        *,
        filter_metadata: dict[str, Any] | None = None,
        include_metadata: bool = True,
    ) -> list[SearchResult]:
        """Return the ``top_k`` nearest records for ``query_vector``."""


class InMemoryVectorStore(BaseVectorStore):
    """Simple in-memory vector store useful for testing and local dev."""

    records: dict[str, VectorRecord] = Field(default_factory=dict)

    async def upsert(self, records: Iterable[VectorRecord]) -> None:
        """Store ``records`` in the in-memory dictionary."""
        for record in records:
            self.records[record.id] = record

    def list_records(self) -> list[VectorRecord]:  # pragma: no cover - helper
        """Return a copy of stored records for inspection."""
        return list(self.records.values())

    async def search(
        self,
        query_vector: list[float],
        top_k: int,
        *,
        filter_metadata: dict[str, Any] | None = None,
        include_metadata: bool = True,
    ) -> list[SearchResult]:
        """Perform cosine-similarity search against stored vectors."""
        if not query_vector:
            msg = "query_vector cannot be empty"
            raise ValueError(msg)

        filtered_records = [
            record
            for record in self.records.values()
            if self._matches_filter(record.metadata, filter_metadata)
        ]
        scores: list[tuple[float, VectorRecord]] = []
        for record in filtered_records:
            score = self._cosine_similarity(query_vector, record.values)
            scores.append((score, record))

        ranked = sorted(scores, key=lambda item: item[0], reverse=True)[:top_k]
        results: list[SearchResult] = []
        for score, record in ranked:
            metadata = record.metadata if include_metadata else {}
            results.append(
                SearchResult(
                    id=record.id,
                    content=record.text,
                    score=max(score, 0.0),
                    metadata=metadata,
                )
            )
        return results

    @staticmethod
    def _matches_filter(
        metadata: dict[str, Any], filter_metadata: dict[str, Any] | None
    ) -> bool:
        if not filter_metadata:
            return True
        for key, expected in filter_metadata.items():
            actual = metadata.get(key)
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if len(a) != len(b):
            msg = "query_vector and stored vector must have the same dimensions"
            raise ValueError(msg)
        dot = sum(x * y for x, y in zip(a, b, strict=True))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


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

    async def search(
        self,
        query_vector: list[float],
        top_k: int,
        *,
        filter_metadata: dict[str, Any] | None = None,
        include_metadata: bool = True,
    ) -> list[SearchResult]:
        """Execute a similarity query against the Pinecone index."""
        client = self._resolve_client()
        index = self._resolve_index(client)
        response = index.query(
            vector=query_vector,
            top_k=top_k,
            namespace=self.namespace,
            filter=filter_metadata,
            include_metadata=include_metadata,
            include_values=False,
        )
        if inspect.iscoroutine(response):
            response = await response

        matches_attr = getattr(response, "matches", None)
        if matches_attr is not None:
            matches = matches_attr
        elif isinstance(response, dict):
            matches = response.get("matches", [])
        else:  # pragma: no cover - defensive guard for unknown response types
            matches = []
        results: list[SearchResult] = []
        for match in matches:
            metadata = match.get("metadata") or {}
            text = metadata.get("text", "")
            results.append(
                SearchResult(
                    id=str(match.get("id")),
                    content=text,
                    score=float(match.get("score", 0.0)),
                    metadata=metadata if include_metadata else {},
                    source="vector",
                )
            )

        return results

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
