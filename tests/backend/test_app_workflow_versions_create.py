"""Tests for creating and ingesting workflow versions."""

from __future__ import annotations
from datetime import UTC, datetime
from uuid import uuid4
import pytest
from fastapi import HTTPException
from orcheo.models.workflow import WorkflowVersion
from orcheo_backend.app import create_workflow_version, ingest_workflow_version
from orcheo_backend.app.repository import WorkflowNotFoundError
from orcheo_backend.app.schemas.workflows import (
    WorkflowVersionCreateRequest,
    WorkflowVersionIngestRequest,
)


@pytest.mark.asyncio()
async def test_create_workflow_version_success() -> None:
    """Create workflow version endpoint creates and returns new version."""

    workflow_id = uuid4()
    version_id = uuid4()

    class Repository:
        async def create_version(self, wf_id, graph, metadata, notes, created_by):
            return WorkflowVersion(
                id=version_id,
                workflow_id=wf_id,
                version=1,
                graph=graph,
                created_by=created_by,
                notes=notes,
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    request = WorkflowVersionCreateRequest(
        graph={"nodes": []},
        metadata={"test": "data"},
        notes="Test version",
        created_by="admin",
    )

    result = await create_workflow_version(workflow_id, request, Repository())

    assert result.id == version_id
    assert result.workflow_id == workflow_id
    assert result.version == 1


@pytest.mark.asyncio()
async def test_create_workflow_version_not_found() -> None:
    """Create workflow version raises 404 for missing workflow."""

    workflow_id = uuid4()

    class Repository:
        async def create_version(self, wf_id, graph, metadata, notes, created_by):
            raise WorkflowNotFoundError("not found")

    request = WorkflowVersionCreateRequest(
        graph={"nodes": []},
        created_by="admin",
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_workflow_version(workflow_id, request, Repository())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_ingest_workflow_version_success() -> None:
    """Ingest workflow version creates version from script."""

    workflow_id = uuid4()
    version_id = uuid4()

    class Repository:
        async def create_version(self, wf_id, graph, metadata, notes, created_by):
            return WorkflowVersion(
                id=version_id,
                workflow_id=wf_id,
                version=1,
                graph=graph,
                created_by=created_by,
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    script_code = (
        "from langgraph.graph import StateGraph\n"
        "graph = StateGraph(dict)\n"
        "graph.add_node('test', lambda x: x)"
    )
    request = WorkflowVersionIngestRequest(
        script=script_code,
        entrypoint="graph",
        created_by="admin",
    )

    result = await ingest_workflow_version(workflow_id, request, Repository())

    assert result.id == version_id


@pytest.mark.asyncio()
async def test_ingest_workflow_version_script_error() -> None:
    """Ingest workflow version handles script ingestion errors."""

    workflow_id = uuid4()

    class Repository:
        async def create_version(self, wf_id, graph, metadata, notes, created_by):
            return WorkflowVersion(
                id=uuid4(),
                workflow_id=wf_id,
                version=1,
                graph=graph,
                created_by=created_by,
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    request = WorkflowVersionIngestRequest(
        script="invalid python code {",
        entrypoint="graph",
        created_by="admin",
    )

    with pytest.raises(HTTPException) as exc_info:
        await ingest_workflow_version(workflow_id, request, Repository())

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio()
async def test_ingest_workflow_version_not_found() -> None:
    """Ingest workflow version raises 404 for missing workflow."""

    workflow_id = uuid4()

    class Repository:
        async def create_version(self, wf_id, graph, metadata, notes, created_by):
            raise WorkflowNotFoundError("not found")

    script_code = (
        "from langgraph.graph import StateGraph\n"
        "graph = StateGraph(dict)\n"
        "graph.add_node('test', lambda x: x)"
    )
    request = WorkflowVersionIngestRequest(
        script=script_code,
        entrypoint="graph",
        created_by="admin",
    )

    with pytest.raises(HTTPException) as exc_info:
        await ingest_workflow_version(workflow_id, request, Repository())

    assert exc_info.value.status_code == 404
