"""Shared helpers for conversational search demos."""

from __future__ import annotations
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import yaml
from orcheo.nodes.conversational_search.models import Document


@dataclass(frozen=True)
class QueryExample:
    """Structured representation of a sample query."""

    id: str
    question: str
    intent: str | None = None
    expected_context: Sequence[str] | None = None


@dataclass(frozen=True)
class GoldenExample:
    """Golden query with an expected answer and citations."""

    id: str
    query: str
    expected_answer: str
    expected_citations: Sequence[str]


@dataclass(frozen=True)
class RelevanceLabel:
    """Sparse relevance label for retrieval evaluation."""

    query_id: str
    doc_id: str
    relevance: int


@dataclass(frozen=True)
class DemoPaths:
    """Resolved paths for a demo configuration and its assets."""

    config: Path
    docs_dir: Path
    queries: Path | None = None
    golden: Path | None = None
    labels: Path | None = None


def load_yaml_config(config_path: Path) -> dict[str, Any]:
    """Load a YAML configuration file into a dictionary."""
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_documents(docs_dir: Path) -> list[Document]:
    """Load markdown documents from a directory into :class:`Document` objects."""
    documents: list[Document] = []
    for path in sorted(docs_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        documents.append(
            Document(
                id=path.stem,
                content=text,
                metadata={"filename": path.name, "path": str(path)},
                source=str(path),
            )
        )
    return documents


def load_queries(queries_path: Path) -> list[QueryExample]:
    """Load sample queries from a JSON list."""
    with queries_path.open("r", encoding="utf-8") as handle:
        raw_queries: Iterable[dict[str, Any]] = json.load(handle)
    queries: list[QueryExample] = []
    for item in raw_queries:
        queries.append(
            QueryExample(
                id=item["id"],
                question=item["question"],
                intent=item.get("intent"),
                expected_context=item.get("expected_context"),
            )
        )
    return queries


def load_golden_examples(golden_path: Path) -> list[GoldenExample]:
    """Load golden queries used for evaluation demos."""
    with golden_path.open("r", encoding="utf-8") as handle:
        raw_examples: Iterable[dict[str, Any]] = json.load(handle)
    examples: list[GoldenExample] = []
    for item in raw_examples:
        examples.append(
            GoldenExample(
                id=item["id"],
                query=item["query"],
                expected_answer=item["expected_answer"],
                expected_citations=item.get("expected_citations", []),
            )
        )
    return examples


def load_relevance_labels(labels_path: Path) -> list[RelevanceLabel]:
    """Load sparse relevance labels for retrieval evaluation."""
    with labels_path.open("r", encoding="utf-8") as handle:
        raw_labels: Iterable[dict[str, Any]] = json.load(handle)
    labels: list[RelevanceLabel] = []
    for item in raw_labels:
        labels.append(
            RelevanceLabel(
                query_id=item["query_id"],
                doc_id=item["doc_id"],
                relevance=int(item["relevance"]),
            )
        )
    return labels


def load_demo_assets(
    paths: DemoPaths,
) -> tuple[dict[str, Any], list[Document], list[QueryExample]]:
    """Load config and sample data for a demo."""
    config = load_yaml_config(paths.config)
    documents = load_documents(paths.docs_dir)
    queries: list[QueryExample] = []
    if paths.queries and paths.queries.exists():
        queries = load_queries(paths.queries)
    return config, documents, queries


def summarize_dataset(
    documents: Sequence[Document], queries: Sequence[QueryExample]
) -> str:
    """Return a human-readable summary of the loaded dataset."""
    doc_names = ", ".join(
        document.metadata.get("filename", document.id) for document in documents
    )
    query_ids = ", ".join(query.id for query in queries)
    return (
        f"Loaded {len(documents)} documents [{doc_names}] and "
        f"{len(queries)} queries [{query_ids}]"
    )


def default_demo_paths(demo_root: Path) -> DemoPaths:
    """Construct default paths for a demo based on its root directory."""
    config = demo_root / "config.yaml"
    docs_dir = demo_root.parent / "data" / "docs"
    queries = demo_root.parent / "data" / "queries.json"
    golden = demo_root.parent / "data" / "golden" / "golden_dataset.json"
    labels = demo_root.parent / "data" / "labels" / "relevance_labels.json"
    return DemoPaths(
        config=config,
        docs_dir=docs_dir,
        queries=queries,
        golden=golden,
        labels=labels,
    )
