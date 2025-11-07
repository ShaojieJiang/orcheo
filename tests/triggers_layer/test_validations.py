"""Trigger layer validation and error handling tests."""

from __future__ import annotations
from uuid import uuid4
import pytest
from orcheo.triggers import (
    ManualDispatchItem,
    ManualDispatchRequest,
    TriggerLayer,
    WebhookRequest,
)


def test_error_handling_and_validation() -> None:
    """Error handling validates inputs and logs appropriately."""

    layer = TriggerLayer()
    workflow_id = uuid4()

    with pytest.raises(ValueError, match="workflow_id cannot be None"):
        layer.prepare_webhook_dispatch(
            None,
            WebhookRequest(
                method="POST",
                headers={},
                query_params={},
                payload=None,
            ),
        )

    with pytest.raises(ValueError, match="request cannot be None"):
        layer.prepare_webhook_dispatch(workflow_id, None)

    with pytest.raises(ValueError, match="now parameter cannot be None"):
        layer.collect_due_cron_dispatches(now=None)

    with pytest.raises(ValueError, match="workflow_id cannot be None"):
        layer.commit_cron_dispatch(None)

    with pytest.raises(ValueError, match="request cannot be None"):
        layer.prepare_manual_dispatch(None, default_workflow_version_id=uuid4())

    with pytest.raises(ValueError, match="default_workflow_version_id cannot be None"):
        layer.prepare_manual_dispatch(
            ManualDispatchRequest(
                workflow_id=workflow_id,
                actor="test",
                runs=[ManualDispatchItem()],
            ),
            default_workflow_version_id=None,
        )

    with pytest.raises(ValueError, match="run_id cannot be None"):
        layer.next_retry_for_run(None)
