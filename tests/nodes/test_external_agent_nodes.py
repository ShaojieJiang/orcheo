"""Tests for Claude Code and Codex workflow nodes."""

from __future__ import annotations
import subprocess
from pathlib import Path
import pytest
from orcheo.external_agents.runtime import ExternalAgentRuntimeManager
from orcheo.graph.state import State
from orcheo.nodes.claude_code import ClaudeCodeNode
from orcheo.nodes.codex import CodexNode
from orcheo.nodes.registry import registry
from orcheo.tracing.model_metadata import TRACE_METADATA_KEY
from tests.external_agents.test_runtime import FakeProvider


class FakeCodexRuntimeManager(ExternalAgentRuntimeManager):
    """Runtime manager configured with the fake provider for node tests."""

    provider = FakeProvider(version="1.0.0", authenticated=True)
    runtime_root: Path

    def __init__(self) -> None:
        """Initialize the fake runtime manager."""
        self.provider.name = "codex"
        super().__init__(
            runtime_root=self.runtime_root,
            providers={"codex": self.provider},
        )


class FakeClaudeRuntimeManager(ExternalAgentRuntimeManager):
    """Runtime manager configured with the fake provider for node tests."""

    provider = FakeProvider(version="1.0.0", authenticated=False)
    runtime_root: Path

    def __init__(self) -> None:
        """Initialize the fake runtime manager."""
        self.provider.name = "claude_code"
        super().__init__(
            runtime_root=self.runtime_root,
            providers={"claude_code": self.provider},
        )


@pytest.mark.asyncio
async def test_codex_node_successfully_installs_and_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex node installs a missing runtime and returns normalized success data."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
    FakeCodexRuntimeManager.runtime_root = tmp_path / "runtimes"
    monkeypatch.setattr(CodexNode, "runtime_manager_class", FakeCodexRuntimeManager)
    node = CodexNode(
        name="codex_fix",
        prompt="fix tests",
        working_directory=str(repo),
    )

    result = await node(
        State({"inputs": {}, "results": {}, "messages": []}),
        {},
    )

    payload = result["results"]["codex_fix"]
    assert payload["status"] == "succeeded"
    assert payload["provider"] == "codex"
    assert payload["resolved_version"] == "1.0.0"
    assert payload["stdout"] == "fix tests\n"
    assert result[TRACE_METADATA_KEY]["external_agent"]["provider"] == "codex"
    assert result[TRACE_METADATA_KEY]["external_agent"]["command_path"].endswith(
        "fake-agent"
    )


@pytest.mark.asyncio
async def test_claude_node_returns_setup_needed_when_auth_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Claude node returns structured setup-needed guidance when unauthenticated."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
    FakeClaudeRuntimeManager.runtime_root = tmp_path / "runtimes"
    monkeypatch.setattr(
        ClaudeCodeNode,
        "runtime_manager_class",
        FakeClaudeRuntimeManager,
    )
    node = ClaudeCodeNode(
        name="claude_review",
        prompt="review diff",
        working_directory=str(repo),
    )

    result = await node(
        State({"inputs": {}, "results": {}, "messages": []}),
        {},
    )

    payload = result["results"]["claude_review"]
    assert payload["status"] == "setup_needed"
    assert payload["reason"] == "auth_required"
    assert payload["commands"] == ["fake-agent login"]
    assert payload["resolved_version"] == "1.0.0"


@pytest.mark.asyncio
async def test_codex_node_normalizes_timeout_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Timeouts terminate the process tree and retain normalized failure fields."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
    FakeCodexRuntimeManager.runtime_root = tmp_path / "runtimes"
    monkeypatch.setattr(CodexNode, "runtime_manager_class", FakeCodexRuntimeManager)
    node = CodexNode(
        name="codex_timeout",
        prompt="timeout please",
        working_directory=str(repo),
        timeout_seconds=1,
    )

    result = await node(
        State({"inputs": {}, "results": {}, "messages": []}),
        {},
    )

    payload = result["results"]["codex_timeout"]
    assert payload["status"] == "failed"
    assert payload["reason"] == "timeout"
    assert payload["message"] == "codex timed out after 1 seconds."


def test_external_agent_nodes_registered() -> None:
    """Both external agent nodes are registered in the global node registry."""
    claude_metadata = registry.get_metadata("ClaudeCodeNode")
    codex_metadata = registry.get_metadata("CodexNode")

    assert claude_metadata is not None
    assert claude_metadata.category == "ai"
    assert codex_metadata is not None
    assert codex_metadata.category == "ai"
