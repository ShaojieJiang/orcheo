"""Tests for workflow input helpers."""

from __future__ import annotations
from orcheo_sdk.cli.workflow.inputs import _cache_notice
from tests.sdk.workflow_cli_test_utils import make_state


def test_cache_notice_human_mode() -> None:
    state = make_state()
    _cache_notice(state, "workflow wf-1", stale=False)
    assert state.console.messages
    assert "Using cached data" in state.console.messages[-1]


def test_cache_notice_machine_mode() -> None:
    state = make_state()
    state.human = False
    _cache_notice(state, "workflow wf-1", stale=False)
    assert state.console.messages == []
