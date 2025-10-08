"""Workflow authoring primitives for the Orcheo Python SDK."""

from __future__ import annotations
import asyncio
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar, Generic, Literal, TypeVar
from pydantic import BaseModel


ConfigT = TypeVar("ConfigT", bound=BaseModel)
OutputT = TypeVar("OutputT")


@dataclass(slots=True)
class WorkflowState:
    """Runtime view of workflow inputs and generated outputs."""

    inputs: Mapping[str, Any]
    outputs: MutableMapping[str, Any]

    def get_input(self, key: str, default: Any | None = None) -> Any:
        """Return an input value or a default when not provided."""
        if key in self.inputs:
            return self.inputs[key]
        return default

    def get_output(self, node_name: str) -> Any:
        """Return the output produced by a prior node."""
        return self.outputs[node_name]

    def snapshot(self) -> dict[str, Any]:
        """Return a merged snapshot of inputs and outputs."""
        return {**self.inputs, **self.outputs}


@dataclass(slots=True)
class WorkflowRunContext:
    """Metadata passed to each node invocation."""

    execution_id: str | None
    metadata: Mapping[str, Any]


@dataclass(slots=True)
class WorkflowRunResult:
    """Result returned from executing a workflow locally."""

    outputs: dict[str, Any]
    run_order: list[str]

    def get_output(self, node_name: str) -> Any:
        """Return the output for an individual node."""
        return self.outputs[node_name]


@dataclass(slots=True)
class DeploymentRequest:
    """Representation of a workflow deployment HTTP request."""

    method: Literal["POST", "PUT"]
    url: str
    json: dict[str, Any]
    headers: dict[str, str]


class WorkflowNode(Generic[ConfigT, OutputT], ABC):
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

    @abstractmethod
    async def run(
        self, state: WorkflowState, context: WorkflowRunContext
    ) -> OutputT:  # pragma: no cover - subclasses override
        """Execute the node using the latest workflow state."""
        raise NotImplementedError

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
    """Utility for composing and running workflows programmatically.

    The :meth:`run` and :meth:`arun` helpers execute workflows entirely in-process.
    They provide a lightweight way to validate node logic locally before exporting
    and deploying the workflow to the managed Orcheo runtime. Production
    executions should continue to happen through the backend once a workflow is
    deployed.
    """

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
        self._nodes: dict[str, WorkflowNode[Any, Any]] = {}
        self._dependencies: dict[str, set[str]] = {}
        self._dependents: dict[str, set[str]] = {}
        self._metadata: dict[str, Any] = dict(metadata or {})

    @property
    def metadata(self) -> Mapping[str, Any]:
        """Return workflow-level metadata."""
        return dict(self._metadata)

    def add_node(
        self,
        node: WorkflowNode[Any, Any],
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

    def nodes(self) -> list[WorkflowNode[Any, Any]]:
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

    async def arun(
        self,
        inputs: Mapping[str, Any] | None = None,
        *,
        execution_id: str | None = None,
    ) -> WorkflowRunResult:
        """Execute the workflow asynchronously with the provided inputs.

        This is intended for local validation or test harnesses. Deployed
        workflows should be triggered via the Orcheo service rather than this
        client-side runner.
        """
        state = WorkflowState(inputs=dict(inputs or {}), outputs={})
        indegree: dict[str, int] = {
            node_name: len(dependencies)
            for node_name, dependencies in self._dependencies.items()
        }
        ready = deque(sorted(name for name, degree in indegree.items() if degree == 0))
        run_order: list[str] = []

        while ready:
            current = ready.popleft()
            node = self._nodes[current]
            context = WorkflowRunContext(
                execution_id=execution_id,
                metadata=self._metadata,
            )
            result = await node.run(state, context)
            state.outputs[current] = result
            run_order.append(current)
            for dependent in sorted(self._dependents.get(current, set())):
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)

        if len(run_order) != len(self._nodes):
            unresolved = sorted(
                node_name for node_name in self._nodes if node_name not in run_order
            )
            msg = (
                "workflow execution did not finish; dependency cycle detected for "
                f"nodes: {', '.join(unresolved)}"
            )
            raise RuntimeError(msg)

        return WorkflowRunResult(outputs=dict(state.outputs), run_order=run_order)

    def run(
        self,
        inputs: Mapping[str, Any] | None = None,
        *,
        execution_id: str | None = None,
    ) -> WorkflowRunResult:
        """Synchronous helper that wraps :meth:`arun`.

        Examples:
            Basic synchronous execution::

                workflow = Workflow(name="data_pipeline")
                # ... add nodes to workflow ...

                # Run synchronously (blocks until completion)
                result = workflow.run(inputs={"user_id": 123})
                print(f"Final output: {result.get_output('final_node')}")

            Asynchronous execution for better performance::

                async def main():
                    workflow = Workflow(name="data_pipeline")
                    # ... add nodes to workflow ...

                    # Run asynchronously (non-blocking)
                    result = await workflow.arun(inputs={"user_id": 123})
                    print(f"Execution order: {result.run_order}")
                    return result

                # Run the async function
                result = asyncio.run(main())

            Note: Cannot call run() from within an async context. Use arun() instead::

                async def invalid_usage():
                    workflow = Workflow(name="example")
                    # This will raise RuntimeError:
                    # result = workflow.run()  # ❌ Not allowed in async context

                    # Use this instead:
                    result = await workflow.arun()  # ✅ Correct async usage

        These helpers are designed for local validation before deploying the
        workflow to the managed Orcheo runtime.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:  # pragma: no cover - defensive branch
            msg = (
                "workflow.run() cannot be invoked while an event loop is running; "
                "use `await workflow.arun(...)` instead"
            )
            raise RuntimeError(msg)

        return asyncio.run(self.arun(inputs=inputs, execution_id=execution_id))
