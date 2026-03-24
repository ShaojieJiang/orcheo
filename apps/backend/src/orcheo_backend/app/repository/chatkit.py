"""Shared workflow ChatKit metadata mutation helpers."""

from __future__ import annotations
from typing import Any
from orcheo.models.workflow import ChatKitStartScreenPrompt, Workflow


def apply_chatkit_start_screen_prompts_update(
    workflow: Workflow,
    metadata: dict[str, Any],
    *,
    chatkit_start_screen_prompts: list[ChatKitStartScreenPrompt] | None = None,
    clear_chatkit_start_screen_prompts: bool = False,
) -> None:
    """Apply ChatKit starter-prompt changes to a workflow and audit metadata."""
    if clear_chatkit_start_screen_prompts:
        if workflow.chatkit_start_screen_prompts is not None:
            metadata["chatkit_start_screen_prompts"] = {
                "from": [
                    prompt.model_dump(mode="json")
                    for prompt in workflow.chatkit_start_screen_prompts
                ],
                "to": None,
            }
            workflow.chatkit_start_screen_prompts = None
        return

    if chatkit_start_screen_prompts is None:
        return

    current_prompts = workflow.chatkit_start_screen_prompts
    current_payload = (
        [prompt.model_dump(mode="json") for prompt in current_prompts]
        if current_prompts is not None
        else None
    )
    next_payload = [
        prompt.model_dump(mode="json") for prompt in chatkit_start_screen_prompts
    ]
    if next_payload == current_payload:
        return

    metadata["chatkit_start_screen_prompts"] = {
        "from": current_payload,
        "to": next_payload,
    }
    workflow.chatkit_start_screen_prompts = [
        prompt.model_copy(deep=True) for prompt in chatkit_start_screen_prompts
    ]
