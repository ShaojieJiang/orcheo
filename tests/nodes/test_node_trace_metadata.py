"""Tests covering BaseNode trace helpers."""

from __future__ import annotations
import pytest
from orcheo.nodes.base import AINode, BaseRunnable, NoOpTaskNode
from orcheo.tracing.model_metadata import TRACE_METADATA_KEY


class DummyRunnable(BaseRunnable):
    ai_model: str | None = None


class ExplodingAINode(AINode):
    async def run(self, state, config):
        raise RuntimeError("boom")


def test_runtime_run_updates_skips_when_model_matches() -> None:
    runnable = DummyRunnable(name="dummy", ai_model="foo")

    updates = runnable._runtime_run_updates({"configurable": {"chatkit_model": "foo"}})

    assert updates == {}


def test_runtime_run_updates_applies_override() -> None:
    runnable = DummyRunnable(name="dummy", ai_model="foo")

    updates = runnable._runtime_run_updates(
        {"configurable": {"chatkit_model": "bar  "}}
    )

    assert updates == {"ai_model": "bar"}


def test_chatkit_selected_model_normalizes_strings() -> None:
    assert (
        DummyRunnable._chatkit_selected_model(
            {"configurable": {"chatkit_model": "  baz  "}}
        )
        == "baz"
    )
    assert (
        DummyRunnable._chatkit_selected_model({"configurable": {"chatkit_model": None}})
        is None
    )
    assert DummyRunnable._chatkit_selected_model(None) is None


def test_attach_trace_metadata_merges_existing_values() -> None:
    node = NoOpTaskNode(name="noop")
    node._set_trace_metadata_for_run({"custom": {"flag": True}})

    base_result = {"value": 1, TRACE_METADATA_KEY: {"existing": {"ok": True}}}

    merged = node._attach_trace_metadata(base_result)

    assert TRACE_METADATA_KEY in merged
    assert merged[TRACE_METADATA_KEY]["existing"]["ok"] is True
    assert merged[TRACE_METADATA_KEY]["custom"]["flag"] is True


def test_attach_trace_metadata_clears_metadata_for_non_mapping() -> None:
    node = NoOpTaskNode(name="noop")
    node._set_trace_metadata_for_run({"custom": {"flag": True}})

    result = node._attach_trace_metadata("value")

    assert result == "value"
    assert "_trace_metadata_for_run" not in node.__dict__


@pytest.mark.asyncio
async def test_ainode_clears_metadata_on_error() -> None:
    node = ExplodingAINode(name="fail", ai_model="provider:model")

    with pytest.raises(RuntimeError, match="boom"):
        await node.__call__({}, None)


def test_set_trace_metadata_clears_when_empty_dict() -> None:
    """_set_trace_metadata_for_run with empty dict pops the key (lines 321-322)."""
    node = NoOpTaskNode(name="noop")
    node._set_trace_metadata_for_run({"key": "value"})
    assert "_trace_metadata_for_run" in node.__dict__

    node._set_trace_metadata_for_run({})

    assert "_trace_metadata_for_run" not in node.__dict__


def test_set_trace_metadata_clears_when_none() -> None:
    """_set_trace_metadata_for_run with None pops the key (lines 321-322)."""
    node = NoOpTaskNode(name="noop")
    node._set_trace_metadata_for_run({"key": "value"})

    node._set_trace_metadata_for_run(None)

    assert "_trace_metadata_for_run" not in node.__dict__


def test_attach_trace_metadata_merges_overlapping_mapping_keys() -> None:
    """Overlapping Mapping keys in existing trace are deep-merged (line 380)."""
    node = NoOpTaskNode(name="noop")
    node._set_trace_metadata_for_run({"ai": {"extra": "info"}})

    base_result = {
        "value": 1,
        TRACE_METADATA_KEY: {"ai": {"existing": True}},
    }

    merged = node._attach_trace_metadata(base_result)

    assert merged[TRACE_METADATA_KEY]["ai"]["existing"] is True
    assert merged[TRACE_METADATA_KEY]["ai"]["extra"] == "info"
