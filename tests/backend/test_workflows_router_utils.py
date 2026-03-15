"""Tests for workflow router helper utilities."""

from __future__ import annotations
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException
from orcheo_backend.app.repository.errors import WorkflowNotFoundError
from orcheo_backend.app.routers import workflows as workflow_router
from orcheo_backend.app.routers.workflows import get_workflow_canvas


@pytest.mark.parametrize(
    "graph",
    [
        None,
        "not a dict",
        42,
        {"index": None},
        {"index": {"mermaid": 123}},
        {"index": {"mermaid": ""}},
        {"index": {"mermaid": "   "}},
        {"index": {"other": "value"}},
    ],
)
def test_extract_index_mermaid_handles_invalid_graphs(graph: object) -> None:
    assert workflow_router._extract_index_mermaid(graph) is None


def test_extract_index_mermaid_returns_mermaid_string() -> None:
    mermaid = "graph LR"
    graph = {"index": {"mermaid": mermaid}}

    assert workflow_router._extract_index_mermaid(graph) == mermaid


def test_extract_index_mermaid_preserves_whitespace() -> None:
    mermaid = "  graph LR    "
    graph = {"index": {"mermaid": mermaid}}

    assert workflow_router._extract_index_mermaid(graph) == mermaid


class _MissingWorkflowRepository:
    """Repository that resolves workflows but fails to load them."""

    def __init__(self) -> None:
        self._workflow_id = uuid4()

    async def resolve_workflow_ref(
        self,
        workflow_ref: str,
        *,
        include_archived: bool = True,
    ) -> UUID:  # pragma: no cover - stub
        return self._workflow_id

    async def get_workflow(self, workflow_id: UUID) -> None:  # pragma: no cover - stub
        raise WorkflowNotFoundError(str(workflow_id))

    async def list_versions(
        self, workflow_id: UUID
    ) -> list[object]:  # pragma: no cover - stub
        return []


@pytest.mark.asyncio()
async def test_get_workflow_canvas_returns_not_found_when_missing() -> None:
    repository = _MissingWorkflowRepository()

    with pytest.raises(HTTPException) as exc_info:
        await get_workflow_canvas("canvas-flow", repository)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Workflow not found"
