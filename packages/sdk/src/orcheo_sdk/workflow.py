"""Workflow authoring primitives for the Orcheo Python SDK."""

from __future__ import annotations
from abc import ABC
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar, Generic, Literal, TypeVar
from pydantic import BaseModel


ConfigT = TypeVar("ConfigT", bound=BaseModel)


@dataclass(slots=True)
class DeploymentRequest:
    """Representation of a workflow deployment HTTP request."""

    method: Literal["POST", "PUT"]
    url: str
    json: dict[str, Any]
    headers: dict[str, str]


class WorkflowNode(Generic[ConfigT], ABC):
    """Base class for authoring typed workflow nodes."""

    type_name: ClassVar[str]

    def __init__(self, name: str, config: ConfigT):
        """Initialise the node with a unique name and validated configuration."""
        if not name or not name.strip():
            msg = "node name cannot be empty"
            raise ValueError(msg)
        if not isinstance(config, BaseModel):
            msg = "config must be a pydantic.BaseModel instance"
            raise TypeError(msg)
        type_name = getattr(self, "type_name", "").strip()
        if not type_name:
            msg = "WorkflowNode subclasses must define a non-empty type_name"
            raise ValueError(msg)
        self.name = name
        self.config = config

    def export(self) -> dict[str, Any]:
        """Return the JSON-serialisable representation of the node."""
        payload = {"name": self.name, "type": self.type_name}
        payload.update(self.config.model_dump(mode="json"))
        return payload

    def model_json_schema(self) -> dict[str, Any]:
        """Return the JSON schema describing the node configuration."""
        return self.config.model_json_schema()

    def __repr__(self) -> str:
        """Return a debug-friendly representation of the node."""
        return f"{self.__class__.__name__}(name={self.name!r}, type={self.type_name!r})"


class Workflow:
    """Utility for composing workflows programmatically."""

    def __init__(
        self,
        *,
        name: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        """Create a workflow with optional metadata used during deployment."""
        if not name or not name.strip():
            msg = "workflow name cannot be empty"
            raise ValueError(msg)
        self.name = name
        self._nodes: dict[str, WorkflowNode[Any]] = {}
        self._dependencies: dict[str, set[str]] = {}
        self._dependents: dict[str, set[str]] = {}
        self._metadata: dict[str, Any] = dict(metadata or {})

    @property
    def metadata(self) -> Mapping[str, Any]:
        """Return workflow-level metadata."""
        return dict(self._metadata)

    def add_node(
        self,
        node: WorkflowNode[Any],
        *,
        depends_on: Sequence[str] | None = None,
    ) -> None:
        """Register a node with optional dependencies.

        Each dependency expresses an edge from the upstream node to ``node`` in the
        exported graph configuration. Nodes without dependencies automatically
        connect to the special ``START`` vertex, while terminal nodes connect to
        ``END``.
        """
        name = node.name
        if name in self._nodes:
            msg = f"node with name '{name}' already exists"
            raise ValueError(msg)
        deps = tuple(depends_on or ())
        missing = [dependency for dependency in deps if dependency not in self._nodes]
        if missing:
            missing_str = ", ".join(sorted(missing))
            msg = f"dependencies must reference existing nodes: {missing_str}"
            raise ValueError(msg)

        self._nodes[name] = node
        self._dependencies[name] = set(deps)
        for dependency in deps:
            self._dependents.setdefault(dependency, set()).add(name)
        self._dependents.setdefault(name, set())

    def nodes(self) -> list[WorkflowNode[Any]]:
        """Return the nodes registered in insertion order."""
        return [self._nodes[name] for name in self._nodes]

    def to_graph_config(self) -> dict[str, Any]:
        """Return the LangGraph compatible graph configuration."""
        nodes = [node.export() for node in self.nodes()]
        edges: set[tuple[str, str]] = set()
        for node_name, dependencies in self._dependencies.items():
            if dependencies:
                for dependency in dependencies:
                    edges.add((dependency, node_name))
            else:
                edges.add(("START", node_name))
        terminal_nodes = [
            name for name, dependents in self._dependents.items() if not dependents
        ]
        for node_name in terminal_nodes:
            edges.add((node_name, "END"))
        edge_list = sorted(edges)
        return {"nodes": nodes, "edges": edge_list}

    def to_deployment_payload(
        self, *, metadata: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        """Return the payload expected by the deployment API."""
        merged_metadata: dict[str, Any] = {**self._metadata}
        if metadata:
            merged_metadata.update(metadata)
        payload: dict[str, Any] = {
            "name": self.name,
            "graph": self.to_graph_config(),
        }
        if merged_metadata:
            payload["metadata"] = merged_metadata
        return payload

    # Local execution helpers intentionally omitted. Workflows should be
    # deployed and executed via the Orcheo service.
