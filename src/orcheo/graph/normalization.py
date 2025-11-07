"""Utilities for normalising graph configuration structures."""

from __future__ import annotations
from collections.abc import Iterable, Mapping
from typing import Any
from langgraph.graph import END, START


def normalise_edges(edges: Iterable[Any]) -> list[tuple[str, str]]:
    """Return list of (source, target) tuples for the given edge entries."""
    normalised: list[tuple[str, str]] = []
    for entry in edges:
        if isinstance(entry, Mapping):
            source = entry.get("source")
            target = entry.get("target")
        else:
            try:
                source, target = entry  # type: ignore[misc]
            except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
                msg = f"Invalid edge entry: {entry!r}"
                raise ValueError(msg) from exc

        if not isinstance(source, str) or not isinstance(target, str):
            msg = f"Edge endpoints must be strings: {entry!r}"
            raise ValueError(msg)
        normalised.append((source, target))
    return normalised


def normalise_vertex(name: str) -> Any:
    """Map sentinel vertex names to LangGraph constants."""
    if name == "START":
        return START
    if name == "END":
        return END
    return name
