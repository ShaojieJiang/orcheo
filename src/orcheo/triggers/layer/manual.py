"""Manual dispatch helpers for the trigger layer."""

from __future__ import annotations
from uuid import UUID
from orcheo.triggers.layer.models import ManualDispatchPlan
from orcheo.triggers.layer.state import TriggerLayerState
from orcheo.triggers.manual import ManualDispatchRequest


class ManualDispatchMixin(TriggerLayerState):
    """Provide manual dispatch planning helpers."""

    def prepare_manual_dispatch(
        self, request: ManualDispatchRequest, *, default_workflow_version_id: UUID
    ) -> ManualDispatchPlan:
        """Resolve manual dispatch runs and return the dispatch plan."""
        if request is None:
            raise ValueError("request cannot be None")
        if default_workflow_version_id is None:
            raise ValueError("default_workflow_version_id cannot be None")

        try:
            resolved_runs = request.resolve_runs(
                default_workflow_version_id=default_workflow_version_id
            )
            return ManualDispatchPlan(
                triggered_by=request.trigger_label(),
                actor=request.actor,
                runs=resolved_runs,
            )
        except Exception as exc:  # pragma: no cover - logging path
            self._logger.error("Failed to prepare manual dispatch: %s", exc)
            raise


__all__ = ["ManualDispatchMixin"]
