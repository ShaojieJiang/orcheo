"""Vector store abstractions used by conversational search nodes."""

from __future__ import annotations
import inspect
from abc import ABC, abstractmethod
from collections.abc import Iterable
from math import sqrt
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
        query: list[float],
        *,
        top_k: int,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Return ``top_k`` most similar records to the ``query`` vector."""


class InMemoryVectorStore(BaseVectorStore):
    """Simple in-memory vector store useful for testing and local dev."""

    records: dict[str, VectorRecord] = Field(default_factory=dict)

    async def upsert(self, records: Iterable[VectorRecord]) -> None:
        """Store ``records`` in the in-memory dictionary."""
        for record in records:
            self.records[record.id] = record

    async def search(
        self,
        query: list[float],
        *,
        top_k: int,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Return matches using cosine similarity over stored vectors."""

        def matches_filter(record: VectorRecord) -> bool:
            if not filter_metadata:
                return True
            return all(
                record.metadata.get(key) == value
                for key, value in filter_metadata.items()
            )

        scored: list[SearchResult] = []
        for record in self.records.values():
            if not matches_filter(record):
                continue
            score = self._cosine_similarity(query, record.values)
            scored.append(
                SearchResult(
                    id=record.id,
                    score=score,
                    text=record.text,
                    metadata=record.metadata,
                    source="vector",
                )
            )

        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

    @staticmethod
    def _cosine_similarity(query: list[float], values: list[float]) -> float:
        if len(query) != len(values):
            msg = "Query vector length must match stored vectors"
            raise ValueError(msg)
        numerator = sum(q * v for q, v in zip(query, values, strict=True))
        denom_query = sqrt(sum(q * q for q in query))
        denom_values = sqrt(sum(v * v for v in values))
        if denom_query == 0 or denom_values == 0:
            return 0.0
        return numerator / (denom_query * denom_values)

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

    async def search(
        self,
        query: list[float],
        *,
        top_k: int,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Execute a similarity search against Pinecone."""
        client = self._resolve_client()
        index = self._resolve_index(client)
        result = index.query(
            vector=query,
            top_k=top_k,
            namespace=self.namespace,
            filter=filter_metadata,
            include_metadata=True,
        )
        if inspect.iscoroutine(result):
            result = await result

        matches = getattr(result, "matches", []) or []
        parsed: list[SearchResult] = []
        for match in matches:
            metadata = getattr(match, "metadata", None) or {}
            text = metadata.get("text", "")
            parsed.append(
                SearchResult(
                    id=getattr(match, "id", ""),
                    score=getattr(match, "score", 0.0),
                    text=text,
                    metadata=metadata,
                    source="vector",
                )
            )
        return parsed

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
