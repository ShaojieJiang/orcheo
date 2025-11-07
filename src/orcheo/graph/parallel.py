"""Helpers for configuring parallel graph branches."""

from __future__ import annotations
from collections.abc import Iterable, Mapping
from typing import Any
from langgraph.graph import StateGraph
from orcheo.graph.normalization import normalise_vertex


def add_parallel_branches(graph: StateGraph, config: Mapping[str, Any]) -> None:
    """Add fan-out/fan-in style parallel branches."""
    source = config.get("source")
    targets = config.get("targets")
    join = config.get("join")

    if not isinstance(source, str) or not source:
        msg = f"Parallel branch requires a source string: {config!r}"
        raise ValueError(msg)
    if isinstance(targets, str) or not isinstance(targets, Iterable):
        msg = f"Parallel branch requires a list of targets: {config!r}"
        raise ValueError(msg)

    normalised_source = normalise_vertex(source)
    target_list = list(targets)
    normalised_targets = []
    for target in target_list:
        if not isinstance(target, str):
            msg = f"Parallel branch targets must be strings: {config!r}"
            raise ValueError(msg)
        normalised_targets.append(normalise_vertex(target))
    if not normalised_targets:
        msg = f"Parallel branch targets must be strings: {config!r}"
        raise ValueError(msg)

    for target in normalised_targets:
        graph.add_edge(normalised_source, target)

    if isinstance(join, str) and join:
        join_vertex = normalise_vertex(join)
        for target in normalised_targets:
            graph.add_edge(target, join_vertex)
