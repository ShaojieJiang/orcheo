"""Compatibility tests for legacy workflow ChatKit payloads."""

from __future__ import annotations
from orcheo.models import Workflow


def test_workflow_backfills_legacy_chatkit_fields() -> None:
    workflow = Workflow.model_validate(
        {
            "name": "Legacy ChatKit Flow",
            "chatkit_start_screen_prompts": [
                {"label": "Summarize", "prompt": "Summarize the latest results."}
            ],
            "chatkit_supported_models": [{"id": "gpt-5.4", "default": True}],
        }
    )

    assert workflow.chatkit is not None
    assert workflow.chatkit.start_screen_prompts is not None
    assert workflow.chatkit.start_screen_prompts[0].label == "Summarize"
    assert workflow.chatkit.supported_models is not None
    assert workflow.chatkit.supported_models[0].id == "gpt-5.4"


def test_workflow_ignores_legacy_chatkit_fields_when_chatkit_exists() -> None:
    workflow = Workflow.model_validate(
        {
            "name": "Explicit ChatKit Flow",
            "chatkit": {
                "start_screen_prompts": [
                    {"label": "Draft", "prompt": "Draft an email reply."}
                ]
            },
            "chatkit_start_screen_prompts": None,
        }
    )

    assert workflow.chatkit is not None
    assert workflow.chatkit.start_screen_prompts is not None
    assert workflow.chatkit.start_screen_prompts[0].label == "Draft"
