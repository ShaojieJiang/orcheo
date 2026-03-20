from __future__ import annotations
import subprocess
from pathlib import Path
from types import SimpleNamespace
import pytest
import typer
from rich.console import Console
from typer.testing import CliRunner
from orcheo.plugins import PluginImpactSummary
from orcheo_sdk.cli import plugin as plugin_module


class DummyState:
    def __init__(self, human: bool) -> None:
        self.human = human
        self.console = Console(record=True)


def test_resolve_stack_project_dir_prefers_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    stack_dir = tmp_path / "stack"
    monkeypatch.setenv("ORCHEO_STACK_DIR", str(stack_dir))
    assert plugin_module._resolve_stack_project_dir() == stack_dir


def test_resolve_stack_project_dir_defaults_to_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("ORCHEO_STACK_DIR", raising=False)
    monkeypatch.setattr(plugin_module.Path, "home", staticmethod(lambda: tmp_path))
    assert plugin_module._resolve_stack_project_dir() == tmp_path / ".orcheo" / "stack"


def test_stack_compose_base_args_requires_compose_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    stack_dir = tmp_path / "stack"
    stack_dir.mkdir()
    monkeypatch.setenv("ORCHEO_STACK_DIR", str(stack_dir))
    with pytest.raises(typer.BadParameter):
        plugin_module._stack_compose_base_args()


def test_stack_compose_base_args_returns_args(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    stack_dir = tmp_path / "stack"
    stack_dir.mkdir()
    compose_file = stack_dir / "docker-compose.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    monkeypatch.setenv("ORCHEO_STACK_DIR", str(stack_dir))
    assert plugin_module._stack_compose_base_args() == [
        "docker",
        "compose",
        "-f",
        str(compose_file),
        "--project-directory",
        str(stack_dir),
    ]


def test_normalize_runtime_invalid() -> None:
    with pytest.raises(typer.BadParameter):
        plugin_module._normalize_runtime("invalid")


def test_use_stack_runtime_variants(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    stack_dir = tmp_path / "stack"
    stack_dir.mkdir()
    (stack_dir / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    monkeypatch.setattr(plugin_module, "_resolve_stack_project_dir", lambda: stack_dir)
    assert plugin_module._use_stack_runtime("local") is False
    assert plugin_module._use_stack_runtime("stack") is True
    assert plugin_module._use_stack_runtime("auto") is True


def test_run_stack_subprocess_requires_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plugin_module.shutil, "which", lambda _: None)
    with pytest.raises(typer.BadParameter):
        plugin_module._run_stack_subprocess(["echo"])


def test_run_stack_subprocess_handles_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(plugin_module.shutil, "which", lambda _: "/usr/bin/docker")

    def fake_run(
        command: list[str], *, check: bool, capture_output: bool, text: bool
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 2, stdout="output", stderr="oops")

    monkeypatch.setattr(plugin_module.subprocess, "run", fake_run)
    with pytest.raises(typer.BadParameter) as excinfo:
        plugin_module._run_stack_subprocess(["cmd"])
    assert "oops" in str(excinfo.value)


def test_stack_plugin_command_exec_and_run(monkeypatch: pytest.MonkeyPatch) -> None:
    base_args = ["docker", "compose", "-f", "compose", "--project-directory", "stack"]
    monkeypatch.setattr(plugin_module, "_stack_compose_base_args", lambda: base_args)
    monkeypatch.setattr(plugin_module, "_running_stack_services", lambda: {"backend"})
    exec_command = plugin_module._stack_plugin_command(args=["list"], human=True)
    assert "exec" in exec_command
    monkeypatch.setattr(plugin_module, "_running_stack_services", lambda: set())
    run_command = plugin_module._stack_plugin_command(args=["list"], human=False)
    assert "run" in run_command


def test_run_stack_plugin_passthrough_emits_output_and_echo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        plugin_module, "_stack_plugin_command", lambda *, args, human: ["cmd"]
    )

    def fake_run(
        command: list[str], *, expected_exit_codes: set[int] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(plugin_module, "_run_stack_subprocess", fake_run)
    echoed: list[str] = []

    def fake_echo(message: str) -> None:
        echoed.append(message)

    monkeypatch.setattr(plugin_module.typer, "echo", fake_echo)
    state = DummyState(human=False)
    plugin_module._run_stack_plugin_passthrough(args=["list"], state=state)
    assert echoed == ["ok"]


def test_run_stack_plugin_passthrough_doctor_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        plugin_module, "_stack_plugin_command", lambda *, args, human: ["cmd"]
    )

    def fake_run(
        command: list[str], *, expected_exit_codes: set[int] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="")

    monkeypatch.setattr(plugin_module, "_run_stack_subprocess", fake_run)
    with pytest.raises(typer.Exit):
        plugin_module._run_stack_plugin_passthrough(
            args=["doctor"], state=DummyState(human=False)
        )


def test_is_local_plugin_ref_detects_variants(tmp_path: Path) -> None:
    file_path = tmp_path / "plugin.txt"
    file_path.write_text("x", encoding="utf-8")
    assert plugin_module._is_local_plugin_ref(str(file_path))
    assert plugin_module._is_local_plugin_ref("./cli")
    assert plugin_module._is_local_plugin_ref("plugin.whl")
    assert plugin_module._is_local_plugin_ref("group/plugin")
    assert not plugin_module._is_local_plugin_ref(
        "git+https://github.com/ShaojieJiang/orcheo-plugin-wecom-listener.git"
    )
    assert not plugin_module._is_local_plugin_ref(
        "git@github.com:ShaojieJiang/orcheo-plugin-wecom-listener.git"
    )


def test_run_stack_plugin_json_parses_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        plugin_module, "_stack_plugin_command", lambda *, args, human: ["cmd"]
    )

    def fake_run(
        command: list[str], *, expected_exit_codes: set[int] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command, 0, stdout='{"ok": true}\n', stderr=""
        )

    monkeypatch.setattr(plugin_module, "_run_stack_subprocess", fake_run)
    assert plugin_module._run_stack_plugin_json(["install"]) == {"ok": True}
    monkeypatch.setattr(
        plugin_module,
        "_run_stack_subprocess",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            [], 0, stdout="", stderr=""
        ),
    )
    assert plugin_module._run_stack_plugin_json(["install"]) is None


def test_restart_running_stack_services(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plugin_module, "_running_stack_services", lambda: set())
    monkeypatch.setattr(
        plugin_module, "_run_stack_subprocess", lambda *args, **kwargs: None
    )
    plugin_module._restart_running_stack_services(DummyState(human=False))
    calls: list[list[str]] = []

    def fake_run(
        command: list[str], *, expected_exit_codes: set[int] | None = None
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    services = {"backend", "worker"}
    monkeypatch.setattr(plugin_module, "_running_stack_services", lambda: services)
    monkeypatch.setattr(plugin_module, "_stack_compose_base_args", lambda: ["docker"])
    monkeypatch.setattr(plugin_module, "_run_stack_subprocess", fake_run)
    state = DummyState(human=True)
    plugin_module._restart_running_stack_services(state)
    assert calls
    assert "Restarted stack services" in state.console.export_text()


def test_payload_requires_restart_checks_types() -> None:
    assert not plugin_module._payload_requires_restart("nope")
    assert plugin_module._payload_requires_restart(
        {"impact": {"restart_required": True}}
    )


def test_impact_to_dict_and_render(monkeypatch: pytest.MonkeyPatch) -> None:
    impact = PluginImpactSummary(
        change_type="install",
        affected_component_kinds=["nodes"],
        affected_component_ids=["node"],
        activation_mode="silent",
        prompt_required=False,
        restart_required=True,
    )
    summary = plugin_module._impact_to_dict(impact)
    assert summary["restart_required"] is True
    printed: list[dict[str, object]] = []

    def fake_render(console: Console, payload: dict[str, object], title: str) -> None:
        printed.append(payload)

    monkeypatch.setattr(plugin_module, "render_json", fake_render)
    state = DummyState(human=True)
    plugin_module._render_impact(state, impact)
    assert printed


def test_maybe_confirm_handles_human_prompts(monkeypatch: pytest.MonkeyPatch) -> None:
    impact = SimpleNamespace(prompt_required=True)
    state = DummyState(human=True)
    monkeypatch.setattr(
        plugin_module.typer, "confirm", lambda prompt, default=False: False
    )
    with pytest.raises(typer.Exit):
        plugin_module._maybe_confirm(
            impact=impact,
            prompt_text="ok?",
            state=state,
            force=False,
        )
    monkeypatch.setattr(
        plugin_module.typer, "confirm", lambda prompt, default=False: True
    )
    plugin_module._maybe_confirm(
        impact=impact,
        prompt_text="ok?",
        state=state,
        force=False,
    )
    plugin_module._maybe_confirm(
        impact=SimpleNamespace(prompt_required=True),
        prompt_text="ok?",
        state=state,
        force=True,
    )


def test_list_command_uses_stack_passthrough(
    runner: CliRunner, env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(plugin_module, "_use_stack_runtime", lambda runtime: True)
    monkeypatch.setattr(plugin_module, "_state", lambda ctx: DummyState(human=True))
    recorded: list[tuple[list[str], DummyState]] = []

    def fake_passthrough(*, args: list[str], state: DummyState) -> None:
        recorded.append((args, state))

    monkeypatch.setattr(
        plugin_module, "_run_stack_plugin_passthrough", fake_passthrough
    )
    runner.invoke(plugin_module.plugin_app, ["list"], env=env)
    assert recorded and recorded[0][0] == ["list"]


def test_show_command_uses_stack_passthrough(
    runner: CliRunner, env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(plugin_module, "_use_stack_runtime", lambda runtime: True)
    monkeypatch.setattr(plugin_module, "_state", lambda ctx: DummyState(human=True))
    recorded: list[tuple[list[str], DummyState]] = []

    def fake_passthrough(*, args: list[str], state: DummyState) -> None:
        recorded.append((args, state))

    monkeypatch.setattr(
        plugin_module, "_run_stack_plugin_passthrough", fake_passthrough
    )
    runner.invoke(plugin_module.plugin_app, ["show", "ore"], env=env)
    assert recorded and recorded[0][0] == ["show", "ore"]


def test_install_command_stack_path_renders_human_output(
    runner: CliRunner, env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(plugin_module, "_use_stack_runtime", lambda runtime: True)
    monkeypatch.setattr(plugin_module, "_state", lambda ctx: DummyState(human=True))
    monkeypatch.setattr(plugin_module, "_is_local_plugin_ref", lambda ref: False)
    payload = {
        "plugin": {"name": "pkg"},
        "impact": {
            "change_type": "install",
            "affected_component_kinds": ["nodes"],
            "affected_component_ids": ["node"],
            "activation_mode": "silent",
            "prompt_required": False,
            "restart_required": True,
        },
    }
    monkeypatch.setattr(plugin_module, "_run_stack_plugin_json", lambda args: payload)
    monkeypatch.setattr(
        plugin_module, "_restart_running_stack_services", lambda state: None
    )
    renders: list[dict[str, object]] = []
    monkeypatch.setattr(
        plugin_module, "render_json", lambda console, data, title: renders.append(data)
    )
    impacts: list[PluginImpactSummary] = []
    monkeypatch.setattr(
        plugin_module, "_render_impact", lambda state, impact: impacts.append(impact)
    )
    runner.invoke(plugin_module.plugin_app, ["install", "pkg"], env=env)
    assert renders
    assert impacts
