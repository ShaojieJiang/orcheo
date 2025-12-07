"""Utility helpers for manipulating ChatKit message threads."""

from __future__ import annotations
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID
from chatkit.errors import CustomStreamError
from chatkit.store import Store
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageItem,
    AttachmentBase,
    ThreadMetadata,
    UserMessageItem,
)
from orcheo.config import get_settings
from orcheo_backend.app.chatkit.context import ChatKitRequestContext
from orcheo_backend.app.chatkit.message_utils import (
    collect_text_from_assistant_content,
    collect_text_from_user_content,
)
from orcheo_backend.app.repository import WorkflowRun


async def build_history(
    store: Store[ChatKitRequestContext],
    thread: ThreadMetadata,
    context: ChatKitRequestContext,
) -> list[dict[str, str]]:
    """Return a ChatML-style history from stored thread items."""
    history: list[dict[str, str]] = []
    page = await store.load_thread_items(
        thread.id,
        after=None,
        limit=200,
        order="asc",
        context=context,
    )
    for item in page.data:
        if isinstance(item, UserMessageItem):
            history.append(
                {
                    "role": "user",
                    "content": collect_text_from_user_content(item.content),
                }
            )
        elif isinstance(item, AssistantMessageItem):
            history.append(
                {
                    "role": "assistant",
                    "content": collect_text_from_assistant_content(item.content),
                }
            )
    return history


def require_workflow_id(thread: ThreadMetadata) -> UUID:
    """Return the workflow identifier stored on ``thread``."""
    workflow_value = thread.metadata.get("workflow_id")
    if not workflow_value:
        raise CustomStreamError(
            "No workflow has been associated with this conversation.",
            allow_retry=False,
        )
    try:
        return UUID(str(workflow_value))
    except ValueError as exc:
        raise CustomStreamError(
            "The configured workflow identifier is invalid.",
            allow_retry=False,
        ) from exc


async def resolve_user_item(
    store: Store[ChatKitRequestContext],
    thread: ThreadMetadata,
    item: UserMessageItem | None,
    context: ChatKitRequestContext,
) -> UserMessageItem:
    """Return the most recent user message for the thread."""
    if item is not None:
        return item

    page = await store.load_thread_items(
        thread.id, after=None, limit=1, order="desc", context=context
    )
    for candidate in page.data:
        if isinstance(candidate, UserMessageItem):
            return candidate

    raise CustomStreamError(
        "Unable to locate the user message for this request.",
        allow_retry=False,
    )


def build_inputs_payload(
    thread: ThreadMetadata,
    message_text: str,
    history: list[dict[str, str]],
    user_item: UserMessageItem | None = None,
) -> dict[str, Any]:
    """Construct the workflow input payload with optional file attachments.

    Args:
        thread: The ChatKit thread metadata
        message_text: The user's message text
        history: Conversation history
        user_item: The user message item containing potential attachments

    Returns:
        Input payload for the workflow, including documents if attachments present
    """
    payload: dict[str, Any] = {
        "message": message_text,
        "history": history,
        "thread_id": thread.id,
        "session_id": thread.id,
        "metadata": dict(thread.metadata),
    }

    # Extract file attachments and convert to documents format
    if user_item is not None and hasattr(user_item, "attachments"):
        attachments = getattr(user_item, "attachments", None)
        if attachments and isinstance(attachments, list) and len(attachments) > 0:
            documents: list[dict[str, Any]] = []
            storage_base = _chatkit_storage_base()
            for attachment in attachments:
                # ChatKit attachments from direct upload include file metadata
                if isinstance(attachment, dict):
                    doc = {
                        "content": attachment.get("content", ""),
                        "source": attachment.get("filename", "unknown"),
                        "metadata": {
                            "type": attachment.get("content_type", "text/plain"),
                            "size": attachment.get("size", 0),
                            "file_id": attachment.get("file_id", ""),
                        },
                    }
                    documents.append(doc)
                elif isinstance(attachment, AttachmentBase):
                    storage_path = storage_base / f"{attachment.id}_{attachment.name}"
                    doc = {
                        "storage_path": str(storage_path),
                        "source": attachment.name,
                        "metadata": {
                            "mime_type": attachment.mime_type,
                            "attachment_id": attachment.id,
                        },
                    }
                    documents.append(doc)

            if documents:
                payload["documents"] = documents

    return payload


def _chatkit_storage_base() -> Path:
    """Return the configured storage path for ChatKit uploads."""
    settings = get_settings()
    return Path(
        str(settings.get("CHATKIT_STORAGE_PATH", "~/.orcheo/chatkit"))
    ).expanduser()


def record_run_metadata(thread: ThreadMetadata, run: WorkflowRun | None) -> None:
    """Persist run identifiers on the thread metadata."""
    thread.metadata = {
        **thread.metadata,
        "last_run_at": datetime.now(UTC).isoformat(),
    }
    if "runs" in thread.metadata and isinstance(thread.metadata["runs"], list):
        runs_list = list(thread.metadata["runs"])
    else:
        runs_list = []

    if run is not None:
        runs_list.append(str(run.id))
        thread.metadata["last_run_id"] = str(run.id)

    if runs_list:
        thread.metadata["runs"] = runs_list[-20:]


def build_assistant_item(
    store: Store[ChatKitRequestContext],
    thread: ThreadMetadata,
    reply: str,
    context: ChatKitRequestContext,
) -> AssistantMessageItem:
    """Create a ChatKit assistant message item from the reply text."""
    return AssistantMessageItem(
        id=store.generate_item_id("message", thread, context),
        thread_id=thread.id,
        created_at=datetime.now(UTC),
        content=[AssistantMessageContent(text=reply)],
    )


__all__ = [
    "build_assistant_item",
    "build_history",
    "build_inputs_payload",
    "record_run_metadata",
    "require_workflow_id",
    "resolve_user_item",
]
