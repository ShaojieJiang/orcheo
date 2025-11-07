"""Webhook trigger helpers for the trigger layer."""

from __future__ import annotations
from uuid import UUID
from orcheo.triggers.layer.models import TriggerDispatch
from orcheo.triggers.layer.state import TriggerLayerState
from orcheo.triggers.webhook import (
    WebhookRequest,
    WebhookTriggerConfig,
    WebhookTriggerState,
)


class WebhookTriggerMixin(TriggerLayerState):
    """Provide webhook trigger orchestration helpers."""

    def configure_webhook(
        self, workflow_id: UUID, config: WebhookTriggerConfig
    ) -> WebhookTriggerConfig:
        """Persist webhook configuration for the workflow and return a copy."""
        state = self._webhook_states.setdefault(workflow_id, WebhookTriggerState())
        state.update_config(config)
        return state.config

    def get_webhook_config(self, workflow_id: UUID) -> WebhookTriggerConfig:
        """Return the stored webhook configuration, creating defaults if needed."""
        state = self._webhook_states.setdefault(workflow_id, WebhookTriggerState())
        return state.config

    def prepare_webhook_dispatch(
        self, workflow_id: UUID, request: WebhookRequest
    ) -> TriggerDispatch:
        """Validate an inbound webhook request and return the dispatch payload."""
        if workflow_id is None:
            raise ValueError("workflow_id cannot be None")
        if request is None:
            raise ValueError("request cannot be None")

        try:
            self._ensure_healthy(workflow_id)
            state = self._webhook_states.setdefault(workflow_id, WebhookTriggerState())
            state.validate(request)

            normalized_payload = state.serialize_payload(request.payload)
            normalized_headers = state.scrub_headers_for_storage(
                request.normalized_headers()
            )
            return TriggerDispatch(
                triggered_by="webhook",
                actor="webhook",
                input_payload={
                    "body": normalized_payload,
                    "headers": normalized_headers,
                    "query_params": request.normalized_query(),
                    "source_ip": request.source_ip,
                },
            )
        except Exception as exc:  # pragma: no cover - just logging
            self._logger.error(
                "Failed to prepare webhook dispatch for workflow %s: %s",
                workflow_id,
                exc,
            )
            raise


__all__ = ["WebhookTriggerMixin"]
