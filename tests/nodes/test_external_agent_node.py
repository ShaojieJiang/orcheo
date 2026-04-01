"""Unit tests for the external agent node implementation."""

from __future__ import annotations
from pathlib import Path
from typing import Any
import pytest
from langchain_core.runnables import RunnableConfig
from orcheo.external_agents.models import (
    AuthProbeResult,
    AuthStatus,
    ProcessExecutionResult,
    ResolvedRuntime,
    RuntimeInstallError,
    RuntimeManifest,
    RuntimeResolution,
    RuntimeVerificationError,
    WorkingDirectoryValidationError,
)
from orcheo.graph.state import State
from orcheo.nodes.external_agent import ExternalAgentNode


class DummyProvider:
    name = "dummy_agent"
    display_name = "Dummy Agent"
    package_name = "@tests/dummy"
    executable_name = "dummy-agent"

    def __init__(self, *, authenticated: bool = True) -> None:
        self.authenticated = authenticated

    def probe_auth(
        self,
        runtime: ResolvedRuntime,
        *,
        environ: dict[str, str] | None = None,
    ) -> AuthProbeResult:
        del runtime, environ
        if self.authenticated:
            return AuthProbeResult(status=AuthStatus.AUTHENTICATED)
        return AuthProbeResult(
            status=AuthStatus.SETUP_NEEDED,
            message="login needed",
            commands=["dummy login"],
        )

    def render_login_instructions(self, runtime: ResolvedRuntime) -> list[str]:
        del runtime
        return ["dummy login"]

    def build_command(
        self,
        runtime: ResolvedRuntime,
        *,
        prompt: str,
        system_prompt: str | None = None,
    ) -> list[str]:
        return [runtime.executable_path.name, prompt, system_prompt or ""]

    def build_environment(
        self,
        environ: dict[str, str] | None = None,
    ) -> dict[str, str]:
        return dict(environ or {})


class FakeRuntimeManager:
    def __init__(
        self,
        *,
        provider: DummyProvider,
        resolution: RuntimeResolution | None = None,
        resolve_error: Exception | None = None,
        raise_validate_error: bool = False,
    ) -> None:
        self.provider = provider
        self.resolution = resolution
        self.resolve_error = resolve_error
        self.raise_validate_error = raise_validate_error
        self.mark_auth_called = False
        self.environment: dict[str, str] = {}

    def validate_working_directory(self, candidate: str | Path) -> Path:
        if self.raise_validate_error:
            raise WorkingDirectoryValidationError("invalid workspace")
        return Path(candidate)

    async def resolve_runtime(self, provider_name: str) -> RuntimeResolution:
        if self.resolve_error:
            raise self.resolve_error
        assert self.resolution is not None
        return self.resolution

    def get_provider(self, provider_name: str) -> DummyProvider:
        return self.provider

    def environment_for_provider(self, provider_name: str) -> dict[str, str]:
        return self.environment

    def mark_auth_success(self, provider_name: str) -> RuntimeManifest:
        self.mark_auth_called = True
        assert self.resolution is not None
        return self.resolution.manifest


class DummyExternalAgentNode(ExternalAgentNode):
    provider_name = DummyProvider.name


def _make_runtime_resolution(tmp_path: Path) -> RuntimeResolution:
    runtime_dir = tmp_path / "dummy-runtime"
    return RuntimeResolution(
        runtime=ResolvedRuntime(
            provider=DummyProvider.name,
            version="0.0.1",
            install_dir=runtime_dir,
            executable_path=runtime_dir / "bin" / DummyProvider.executable_name,
            package_name="@tests/dummy",
        ),
        manifest=RuntimeManifest(
            provider=DummyProvider.name,
            provider_root=tmp_path / "provider",
            current_version="0.0.1",
            current_runtime_path=runtime_dir,
        ),
        maintenance_due=False,
    )


def _make_state(inputs: dict[str, Any] | None = None) -> State:
    return State(inputs=inputs or {}, results={}, structured_response=None, config={})


def _make_node(manager: FakeRuntimeManager) -> DummyExternalAgentNode:
    class NodeWithManager(DummyExternalAgentNode):
        runtime_manager_class = staticmethod(lambda: manager)

    node = NodeWithManager(name="test-node", prompt="run")
    node.working_directory = "workspace"
    return node


def test_resolve_prompt_uses_field() -> None:
    node = DummyExternalAgentNode(name="test", prompt="  hello  ")
    assert node._resolve_prompt(_make_state()) == "hello"


def test_resolve_prompt_falls_back_to_inputs() -> None:
    node = DummyExternalAgentNode(name="test")
    assert node._resolve_prompt(_make_state({"message": "  world  "})) == "world"


def test_resolve_prompt_uses_later_input_key_when_earlier_keys_are_blank() -> None:
    node = DummyExternalAgentNode(name="test")
    assert (
        node._resolve_prompt(
            _make_state({"prompt": "   ", "query": None, "input": "  world  "})
        )
        == "world"
    )


def test_resolve_prompt_requires_value() -> None:
    node = DummyExternalAgentNode(name="test")
    with pytest.raises(ValueError):
        node._resolve_prompt(_make_state())


def test_resolve_prompt_requires_value_even_with_blank_input_mapping() -> None:
    node = DummyExternalAgentNode(name="test")
    with pytest.raises(ValueError):
        node._resolve_prompt(
            _make_state(
                {
                    "prompt": "   ",
                    "query": None,
                    "message": "",
                    "input": "   ",
                }
            )
        )


def test_resolve_prompt_requires_value_when_inputs_are_not_a_mapping() -> None:
    node = DummyExternalAgentNode(name="test")
    with pytest.raises(ValueError):
        node._resolve_prompt({"inputs": ["not", "a", "mapping"]})  # type: ignore[arg-type]


def test_resolve_working_directory_requires_value() -> None:
    node = DummyExternalAgentNode(name="test")
    with pytest.raises(ValueError):
        node._resolve_working_directory_input(_make_state())


def test_resolve_working_directory_requires_value_even_with_blank_input_mapping() -> (
    None
):
    node = DummyExternalAgentNode(name="test")
    with pytest.raises(ValueError):
        node._resolve_working_directory_input(
            _make_state(
                {
                    "working_directory": "   ",
                    "workspace": None,
                    "repo_path": "",
                    "path": "   ",
                }
            )
        )


def test_resolve_working_directory_requires_value_when_inputs_are_not_a_mapping() -> (
    None
):
    node = DummyExternalAgentNode(name="test")
    with pytest.raises(ValueError):
        node._resolve_working_directory_input(  # type: ignore[arg-type]
            {"inputs": ["not", "a", "mapping"]}
        )


def test_resolve_working_directory_from_inputs() -> None:
    node = DummyExternalAgentNode(name="test")
    assert (
        node._resolve_working_directory_input(_make_state({"workspace": "  /tmp  "}))
        == "/tmp"
    )


def test_resolve_working_directory_prefers_later_input_when_earlier_blank() -> None:
    node = DummyExternalAgentNode(name="test")
    assert (
        node._resolve_working_directory_input(
            _make_state({"working_directory": "   ", "path": "  /tmp/worktree  "})
        )
        == "/tmp/worktree"
    )


@pytest.mark.asyncio
async def test_run_invalid_configuration_when_working_directory_invalid(
    tmp_path: Path,
) -> None:
    resolution = _make_runtime_resolution(tmp_path)
    manager = FakeRuntimeManager(
        provider=DummyProvider(),
        resolution=resolution,
        raise_validate_error=True,
    )
    node = _make_node(manager)
    state = _make_state({"prompt": "run"})

    result = await node.run(state, RunnableConfig())

    assert result["reason"] == "invalid_configuration"
    assert "invalid workspace" in result["message"]


@pytest.mark.asyncio
async def test_run_reports_install_failure(tmp_path: Path) -> None:
    manager = FakeRuntimeManager(
        provider=DummyProvider(),
        resolve_error=RuntimeInstallError(
            "dummy_agent",
            "install failed",
            command=["install"],
            stdout="out",
            stderr="err",
        ),
    )
    node = _make_node(manager)
    state = _make_state({"prompt": "run"})

    result = await node.run(state, RunnableConfig())

    assert result["reason"] == "install_failed"
    assert result["command"] == ["install"]


@pytest.mark.asyncio
async def test_run_reports_runtime_verification_failure(tmp_path: Path) -> None:
    manager = FakeRuntimeManager(
        provider=DummyProvider(),
        resolve_error=RuntimeVerificationError("failed"),
    )
    node = _make_node(manager)
    state = _make_state({"prompt": "run"})

    result = await node.run(state, RunnableConfig())

    assert result["reason"] == "runtime_verification_failed"


@pytest.mark.asyncio
async def test_run_requires_auth_before_execution(tmp_path: Path) -> None:
    resolution = _make_runtime_resolution(tmp_path)
    manager = FakeRuntimeManager(
        provider=DummyProvider(authenticated=False),
        resolution=resolution,
    )
    node = _make_node(manager)
    state = _make_state({"prompt": "run"})

    result = await node.run(state, RunnableConfig())

    assert result["status"] == "setup_needed"
    assert result["commands"] == ["dummy login"]


@pytest.mark.asyncio
async def test_run_reports_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    resolution = _make_runtime_resolution(tmp_path)
    manager = FakeRuntimeManager(provider=DummyProvider(), resolution=resolution)
    node = _make_node(manager)
    state = _make_state({"prompt": "run"})

    async def fake_execute(*args: object, **kwargs: object) -> ProcessExecutionResult:
        return ProcessExecutionResult(
            command=["dummy"],
            stdout="",
            stderr="",
            exit_code=None,
            timed_out=True,
            duration_seconds=0,
        )

    monkeypatch.setattr(
        "orcheo.nodes.external_agent.execute_process",
        fake_execute,
    )

    result = await node.run(state, RunnableConfig())

    assert result["reason"] == "timeout"
    assert result["status"] == "failed"


@pytest.mark.asyncio
async def test_run_reports_non_zero_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    resolution = _make_runtime_resolution(tmp_path)
    manager = FakeRuntimeManager(provider=DummyProvider(), resolution=resolution)
    node = _make_node(manager)
    state = _make_state({"prompt": "run"})

    async def fake_execute(*args: object, **kwargs: object) -> ProcessExecutionResult:
        return ProcessExecutionResult(
            command=["dummy"],
            stdout="",
            stderr="",
            exit_code=5,
            timed_out=False,
            duration_seconds=0,
        )

    monkeypatch.setattr(
        "orcheo.nodes.external_agent.execute_process",
        fake_execute,
    )

    result = await node.run(state, RunnableConfig())

    assert result["reason"] == "non_zero_exit"
    assert "exited with code 5" in result["message"]


@pytest.mark.asyncio
async def test_run_succeeds_with_zero_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    resolution = _make_runtime_resolution(tmp_path)
    manager = FakeRuntimeManager(provider=DummyProvider(), resolution=resolution)
    node = _make_node(manager)
    state = _make_state({"prompt": "run"})

    async def fake_execute(*args: object, **kwargs: object) -> ProcessExecutionResult:
        return ProcessExecutionResult(
            command=["dummy"],
            stdout="ok",
            stderr="",
            exit_code=0,
            timed_out=False,
            duration_seconds=0,
        )

    monkeypatch.setattr(
        "orcheo.nodes.external_agent.execute_process",
        fake_execute,
    )

    result = await node.run(state, RunnableConfig())

    assert result["status"] == "succeeded"
    assert result["stdout"] == "ok"
