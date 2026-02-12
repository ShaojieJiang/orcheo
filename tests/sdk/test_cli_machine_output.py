"""Tests for machine-readable CLI output (default mode without --human)."""

from __future__ import annotations
import json
from pathlib import Path
import httpx
import pytest
import respx
from typer.testing import CliRunner
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.main import app, run
from orcheo_sdk.cli.output import (
    _escape_md_cell,
    print_json,
    print_machine_success,
    print_markdown_table,
)


# ---------------------------------------------------------------------------
# Helper output functions
# ---------------------------------------------------------------------------


class TestPrintJson:
    def test_dict(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_json({"a": 1, "b": "two"})
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed == {"a": 1, "b": "two"}

    def test_list(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_json([1, 2, 3])
        out = capsys.readouterr().out
        assert json.loads(out) == [1, 2, 3]

    def test_default_serializer(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Non-serializable values fall back to str()."""
        print_json({"path": Path("/tmp/test")})
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["path"] == "/tmp/test"


class TestPrintMarkdownTable:
    def test_basic_table(self, capsys: pytest.CaptureFixture[str]) -> None:
        data = [
            {"name": "Alice", "age": "30"},
            {"name": "Bob", "age": "25"},
        ]
        print_markdown_table(data)
        out = capsys.readouterr().out
        lines = out.strip().split("\n")
        assert len(lines) == 4  # header + separator + 2 rows
        assert "| name | age |" == lines[0]
        assert "| --- | --- |" == lines[1]
        assert "| Alice | 30 |" == lines[2]
        assert "| Bob | 25 |" == lines[3]

    def test_empty_list(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_markdown_table([])
        assert capsys.readouterr().out.strip() == "(empty)"

    def test_pipe_escaping(self, capsys: pytest.CaptureFixture[str]) -> None:
        data = [{"val": "a|b"}]
        print_markdown_table(data)
        out = capsys.readouterr().out
        assert "a\\|b" in out


class TestEscapeMdCell:
    def test_no_pipe(self) -> None:
        assert _escape_md_cell("hello") == "hello"

    def test_pipe(self) -> None:
        assert _escape_md_cell("a|b") == "a\\|b"


class TestPrintMachineSuccess:
    def test_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_machine_success("Done")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed == {"status": "success", "message": "Done"}


# ---------------------------------------------------------------------------
# CLI integration: machine mode (no ORCHEO_HUMAN)
# ---------------------------------------------------------------------------


class TestNodeListMachineMode:
    def test_outputs_markdown_table(
        self, runner: CliRunner, machine_env: dict[str, str]
    ) -> None:
        result = runner.invoke(app, ["node", "list"], env=machine_env)
        assert result.exit_code == 0
        lines = result.stdout.strip().split("\n")
        # Should be markdown table or (empty)
        assert "|" in lines[0] or lines[0] == "(empty)"

    def test_human_flag_outputs_rich(
        self, runner: CliRunner, machine_env: dict[str, str]
    ) -> None:
        result = runner.invoke(app, ["--human", "node", "list"], env=machine_env)
        assert result.exit_code == 0
        # Rich table output has "Available Nodes" title
        assert "Available Nodes" in result.stdout


class TestNodeShowMachineMode:
    def test_outputs_json(self, runner: CliRunner, machine_env: dict[str, str]) -> None:
        result = runner.invoke(app, ["node", "show", "AgentNode"], env=machine_env)
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "name" in data
        assert data["name"] == "AgentNode"


class TestWorkflowListMachineMode:
    def test_outputs_markdown_table(
        self, runner: CliRunner, machine_env: dict[str, str]
    ) -> None:
        payload = [{"id": "wf-1", "name": "Demo", "slug": "demo", "is_archived": False}]
        with respx.mock(assert_all_called=True) as router:
            router.get("http://api.test/api/workflows").mock(
                return_value=httpx.Response(200, json=payload)
            )
            router.get("http://api.test/api/workflows/wf-1/triggers/cron/config").mock(
                return_value=httpx.Response(404)
            )
            result = runner.invoke(app, ["workflow", "list"], env=machine_env)
        assert result.exit_code == 0
        # Should be markdown table
        assert "|" in result.stdout
        assert "Demo" in result.stdout


class TestWorkflowShowMachineMode:
    def test_outputs_json(self, runner: CliRunner, machine_env: dict[str, str]) -> None:
        wf = {"id": "wf-1", "name": "Demo", "slug": "demo"}
        versions: list[dict[str, str]] = []
        runs: list[dict[str, str]] = []
        with respx.mock(assert_all_called=True) as router:
            router.get("http://api.test/api/workflows/wf-1").mock(
                return_value=httpx.Response(200, json=wf)
            )
            router.get("http://api.test/api/workflows/wf-1/versions").mock(
                return_value=httpx.Response(200, json=versions)
            )
            router.get("http://api.test/api/workflows/wf-1/runs").mock(
                return_value=httpx.Response(200, json=runs)
            )
            result = runner.invoke(app, ["workflow", "show", "wf-1"], env=machine_env)
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["workflow"]["name"] == "Demo"


class TestConfigMachineMode:
    def test_outputs_json(self, runner: CliRunner, machine_env: dict[str, str]) -> None:
        result = runner.invoke(app, ["config"], env=machine_env)
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "success"
        assert "profiles" in data
        assert "config_path" in data

    def test_check_outputs_redacted_json(
        self, runner: CliRunner, machine_env: dict[str, str]
    ) -> None:
        config_path = Path(machine_env["ORCHEO_CONFIG_DIR"]) / "cli.toml"
        config_path.write_text(
            "\n".join(
                [
                    "[profiles.default]",
                    'api_url = "http://api.test"',
                    'service_token = "token-123456"',
                    "",
                ]
            ),
            encoding="utf-8",
        )

        check_env = {**machine_env, "ORCHEO_SERVICE_TOKEN": ""}
        result = runner.invoke(app, ["config", "--check"], env=check_env)

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "success"
        assert "config_path" not in data
        assert data["profiles"]["default"]["api_url"] == "http://api.test"
        assert data["profiles"]["default"]["service_token"] == "to...56"


class TestEdgeListMachineMode:
    def test_outputs_markdown_table(
        self, runner: CliRunner, machine_env: dict[str, str]
    ) -> None:
        result = runner.invoke(app, ["edge", "list"], env=machine_env)
        assert result.exit_code == 0
        lines = result.stdout.strip().split("\n")
        assert "|" in lines[0] or lines[0] == "(empty)"


class TestRunErrorMachineMode:
    def test_cli_error_outputs_json(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """In machine mode, CLIError is output as JSON."""

        def mock_app(*args: object, **kwargs: object) -> None:
            raise CLIError("Something went wrong")

        monkeypatch.setattr("orcheo_sdk.cli.main.app", mock_app)
        monkeypatch.delenv("ORCHEO_HUMAN", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            run()
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["error"] == "Something went wrong"

    def test_usage_error_outputs_json(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """In machine mode, UsageError is output as JSON."""
        import click

        def mock_app(*args: object, **kwargs: object) -> None:
            cmd = click.Command("workflow")
            parent_ctx = click.Context(click.Command("orcheo"), info_name="orcheo")
            ctx = click.Context(cmd, parent=parent_ctx, info_name="workflow")
            raise click.UsageError("Missing command.", ctx=ctx)

        monkeypatch.setattr("orcheo_sdk.cli.main.app", mock_app)
        monkeypatch.delenv("ORCHEO_HUMAN", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            run()
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["error"] == "Missing command."
        assert "help" in data


class TestHelpMachineMode:
    def test_top_level_help_plain_text(
        self,
        runner: CliRunner,
        machine_env: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Top-level --help in machine mode uses plain Click formatting."""
        monkeypatch.setattr(app, "rich_markup_mode", None)
        result = runner.invoke(app, ["--help"], env=machine_env)
        assert result.exit_code == 0
        # No Rich panel box-drawing characters
        assert "\u2500" not in result.stdout  # ─
        assert "\u2502" not in result.stdout  # │
        assert "\u256d" not in result.stdout  # ╭
        assert "\u256e" not in result.stdout  # ╮
        # Still contains commands and options
        assert "workflow" in result.stdout
        assert "--help" in result.stdout

    def test_subcommand_help_plain_text(
        self,
        runner: CliRunner,
        machine_env: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Subcommand --help in machine mode uses plain Click formatting."""
        monkeypatch.setattr(app, "rich_markup_mode", None)
        result = runner.invoke(app, ["node", "--help"], env=machine_env)
        assert result.exit_code == 0
        assert "\u256d" not in result.stdout  # ╭
        assert "list" in result.stdout
        assert "show" in result.stdout

    def test_human_help_has_rich_panels(
        self, runner: CliRunner, machine_env: dict[str, str]
    ) -> None:
        """--help with ORCHEO_HUMAN shows Rich panels."""
        human_env = {**machine_env, "ORCHEO_HUMAN": "1"}
        result = runner.invoke(app, ["--help"], env=human_env)
        assert result.exit_code == 0
        # Rich panel has box-drawing characters
        assert "\u2500" in result.stdout  # ─


class TestHumanFlagAndEnv:
    def test_human_env_var(
        self, runner: CliRunner, machine_env: dict[str, str]
    ) -> None:
        """ORCHEO_HUMAN=1 activates human mode."""
        human_env = {**machine_env, "ORCHEO_HUMAN": "1"}
        result = runner.invoke(app, ["node", "list"], env=human_env)
        assert result.exit_code == 0
        assert "Available Nodes" in result.stdout

    def test_human_flag(self, runner: CliRunner, machine_env: dict[str, str]) -> None:
        """--human flag activates human mode."""
        result = runner.invoke(app, ["--human", "node", "list"], env=machine_env)
        assert result.exit_code == 0
        assert "Available Nodes" in result.stdout

    def test_default_is_machine(
        self, runner: CliRunner, machine_env: dict[str, str]
    ) -> None:
        """Without --human or ORCHEO_HUMAN, output is machine-readable."""
        result = runner.invoke(app, ["node", "list"], env=machine_env)
        assert result.exit_code == 0
        # Machine output should not contain Rich table title
        assert "Available Nodes" not in result.stdout


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()
