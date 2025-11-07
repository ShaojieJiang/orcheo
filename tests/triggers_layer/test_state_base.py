"""Trigger layer base class tests."""

from __future__ import annotations
from uuid import uuid4
from orcheo.triggers.layer.state import TriggerLayerState


def test_trigger_layer_state_placeholder_methods() -> None:
    """Ensure abstract mixin stubs remain callable for subclasses."""
    state = TriggerLayerState()

    assert state._maybe_cleanup_states() is None
    assert state._ensure_healthy(uuid4()) is None
