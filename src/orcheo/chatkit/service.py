"""Utilities for orchestrating ChatKit-triggered workflow runs."""

from __future__ import annotations
import logging
from textwrap import shorten
from typing import Any
from uuid import UUID
from orcheo.triggers.manual import ManualDispatchItem, ManualDispatchRequest
from orcheo_backend.app.repository import (
    WorkflowNotFoundError,
    WorkflowRepository,
    WorkflowVersionNotFoundError,
)


LOGGER = logging.getLogger(__name__)


class ChatTriggerService:
    """Bridge between ChatKit conversations and Orcheo workflows."""

    def __init__(self, repository: WorkflowRepository) -> None:
        """Store the workflow repository used for dispatching chat runs."""
        self._repository = repository

    async def handle_message(
        self,
        message: str,
        *,
        workflow_id: str | None,
        node_id: str | None,
        node_label: str | None,
    ) -> str:
        """Dispatch the incoming chat message to a workflow when possible."""
        stripped = message.strip()
        if not stripped:
            return "I didn't receive any text to route to the workflow."

        context: dict[str, Any] = {
            "chat_message": stripped,
            "chat_node_id": node_id,
            "chat_node_label": node_label,
        }

        if not workflow_id:
            return self._acknowledge_without_dispatch(context)

        try:
            workflow_uuid = UUID(workflow_id)
        except ValueError:
            LOGGER.info("Ignoring chat trigger with invalid workflow id", extra=context)
            return self._acknowledge_without_dispatch(
                context,
                "The workflow identifier provided by the canvas isn't valid yet. "
                "Save the workflow before testing the chat trigger.",
            )

        request = ManualDispatchRequest(
            workflow_id=workflow_uuid,
            actor="chatkit",
            label="chat_trigger",
            runs=[ManualDispatchItem(input_payload=context)],
        )

        response: str
        try:
            runs = await self._repository.dispatch_manual_runs(request)
        except WorkflowNotFoundError:
            LOGGER.warning("Chat trigger workflow not found", extra=context)
            response = self._acknowledge_without_dispatch(
                context,
                "I couldn't find that workflow on the server. "
                "Make sure it's been saved and published.",
            )
        except WorkflowVersionNotFoundError:
            LOGGER.warning("Chat trigger workflow has no versions", extra=context)
            response = self._acknowledge_without_dispatch(
                context,
                "The workflow doesn't have an active version yet. "
                "Save a version before testing the chat trigger.",
            )
        except Exception:  # pragma: no cover - defensive logging
            LOGGER.exception("Chat trigger dispatch failed", extra=context)
            response = self._acknowledge_without_dispatch(
                context,
                "Something went wrong while dispatching the workflow run. "
                "Check the server logs for details.",
            )
        else:
            if not runs:
                LOGGER.info("Chat trigger dispatch returned no runs", extra=context)
                response = self._acknowledge_without_dispatch(
                    context,
                    "The workflow repository didn't create a run for this request. "
                    "Verify the workflow configuration and try again.",
                )
            else:
                run = runs[0]
                node_display = node_label or node_id or "chat trigger"
                response = (
                    f"Queued workflow run {run.id} from {node_display}. "
                    f'Message excerpt: "{self._format_message_excerpt(stripped)}". '
                    "Track progress from the execution history panel."
                )

        return response

    @staticmethod
    def _format_message_excerpt(message: str) -> str:
        """Return a shortened representation of the user message."""
        return shorten(message, width=120, placeholder="…")

    @staticmethod
    def _acknowledge_without_dispatch(
        context: dict[str, Any],
        problem: str | None = None,
    ) -> str:
        base = "I'll keep this message handy for when the workflow is ready."
        if problem:
            return f"{problem} {base}".strip()
        node_display = context.get("chat_node_label") or context.get("chat_node_id")
        if node_display:
            return f"Message received for {node_display}. {base}"
        return base
