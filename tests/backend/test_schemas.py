"""Validation tests for FastAPI request schemas."""

from __future__ import annotations
import pytest
from pydantic import ValidationError
from orcheo.graph.ingestion import DEFAULT_SCRIPT_SIZE_LIMIT
from orcheo_backend.app.schemas import WorkflowVersionIngestRequest


def test_workflow_version_ingest_request_rejects_large_scripts() -> None:
    """Submitting scripts larger than the configured limit raises a validation error."""

    oversized = "a" * (DEFAULT_SCRIPT_SIZE_LIMIT + 1)

    with pytest.raises(ValidationError):
        WorkflowVersionIngestRequest(
            script=oversized,
            entrypoint=None,
            metadata={},
            notes=None,
            created_by="tester",
        )
