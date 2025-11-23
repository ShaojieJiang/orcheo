"""Vector store abstractions used by conversational search nodes."""

from __future__ import annotations
import inspect
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from orcheo.nodes.conversational_search.models import VectorRecord


class BaseVectorStore(ABC, BaseModel):
    """Abstract interface for vector store adapters."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @abstractmethod
    async def upsert(self, records: Iterable[VectorRecord]) -> None:
        """Persist ``records`` into the backing vector store."""


class InMemoryVectorStore(BaseVectorStore):
    """Simple in-memory vector store useful for testing and local dev."""

    records: dict[str, VectorRecord] = Field(default_factory=dict)

    async def upsert(self, records: Iterable[VectorRecord]) -> None:
        """Store ``records`` in the in-memory dictionary."""
        for record in records:
            self.records[record.id] = record

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
