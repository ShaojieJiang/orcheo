"""Tests for the Orcheo Vibe workflow template prompt builder."""

from __future__ import annotations
import importlib.util
from pathlib import Path


def _load_vibe_agent_module():
    root = Path(__file__).resolve().parents[2]
    module_path = (
        root
        / "apps"
        / "canvas"
        / "src"
        / "features"
        / "workflow"
        / "data"
        / "templates"
        / "assets"
        / "vibe-agent"
        / "workflow.py"
    )
    spec = importlib.util.spec_from_file_location("vibe_agent_workflow", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_flatten_inputs_prepends_canvas_context_to_conversation() -> None:
    module = _load_vibe_agent_module()

    prompt = module.flatten_inputs(
        {
            "metadata": {
                "context": (
                    "The user is on workflow `wf-123` (Demo Flow). "
                    "Viewing the **Trace** tab."
                )
            },
            "history": [{"role": "assistant", "content": "Previous reply"}],
            "message": "Summarize the latest run.",
        }
    )

    assert prompt.startswith("Canvas context:\n")
    assert "workflow `wf-123` (Demo Flow)" in prompt
    assert "Viewing the **Trace** tab." in prompt
    assert "Conversation:\nassistant: Previous reply" in prompt
    assert "user: Summarize the latest run." in prompt


def test_flatten_inputs_returns_context_when_no_message_is_available() -> None:
    module = _load_vibe_agent_module()

    prompt = module.flatten_inputs(
        {
            "metadata": {
                "context": "The user is creating a new workflow.",
            }
        }
    )

    assert prompt == "Canvas context:\nThe user is creating a new workflow."
