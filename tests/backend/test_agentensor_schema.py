"""Tests for Agentensor checkpoint schemas."""

from __future__ import annotations
from orcheo.agentensor.checkpoints import AgentensorCheckpoint
from orcheo_backend.app.schemas.agentensor import AgentensorCheckpointResponse


def test_checkpoint_response_from_domain() -> None:
    checkpoint = AgentensorCheckpoint(
        workflow_id="workflow-1",
        config_version=2,
        runnable_config={"hello": "world"},
        metrics={"score": 0.9},
        metadata={"env": "test"},
        artifact_url="s3://bucket/checkpoint",
        is_best=True,
    )

    response = AgentensorCheckpointResponse.from_domain(checkpoint)

    assert response.id == checkpoint.id
    assert response.workflow_id == checkpoint.workflow_id
    assert response.config_version == checkpoint.config_version
    assert response.runnable_config == checkpoint.runnable_config
    assert response.metrics == checkpoint.metrics
    assert response.metadata == checkpoint.metadata
    assert response.artifact_url == checkpoint.artifact_url
    assert response.is_best is True
