"""High-level CLI entrypoint tests."""

from __future__ import annotations
import httpx
import pytest
import respx
from typer.testing import CliRunner
from orcheo_sdk.cli.errors import APICallError, CLIError
from orcheo_sdk.cli.main import app, run


def test_main_config_error_handling(runner: CliRunner) -> None:
    # With the default API URL, this should attempt to connect to localhost:8000
    # The test should mock the API call to verify it uses the default
    payload = [{"id": "wf-1", "name": "Demo", "slug": "demo", "is_archived": False}]
    with respx.mock(assert_all_called=True) as router:
        router.get("http://localhost:8000/api/workflows").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = runner.invoke(app, ["workflow", "list"], env={"NO_COLOR": "1"})
    assert result.exit_code == 0
    assert "Demo" in result.stdout


def test_run_cli_error_handling(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def mock_app(*args: object, **kwargs: object) -> None:
        raise CLIError("Test error")

    monkeypatch.setattr("orcheo_sdk.cli.main.app", mock_app)

    with pytest.raises(SystemExit) as exc_info:
        run()
    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "Error: Test error" in captured.out


def test_run_usage_error_handling(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test that UsageError is caught and displayed with a friendly message."""
    import click

    def mock_app(*args: object, **kwargs: object) -> None:
        # Create a command with a proper name
        cmd = click.Command("workflow")
        # Create parent context for "orcheo" with info_name set
        parent_ctx = click.Context(click.Command("orcheo"), info_name="orcheo")
        # Create child context with parent to get "orcheo workflow" path
        ctx = click.Context(cmd, parent=parent_ctx, info_name="workflow")
        raise click.UsageError("Missing command.", ctx=ctx)

    monkeypatch.setattr("orcheo_sdk.cli.main.app", mock_app)

    with pytest.raises(SystemExit) as exc_info:
        run()
    assert exc_info.value.code == 1

    # Verify help command suggestion is printed (covers lines 81-82)
    captured = capsys.readouterr()
    assert "Missing command." in captured.out
    assert "orcheo workflow --help" in captured.out


def test_run_usage_error_without_context(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test that UsageError without context doesn't show help command."""
    import click

    def mock_app(*args: object, **kwargs: object) -> None:
        # Raise UsageError without context
        raise click.UsageError("Invalid option.")

    monkeypatch.setattr("orcheo_sdk.cli.main.app", mock_app)

    with pytest.raises(SystemExit) as exc_info:
        run()
    assert exc_info.value.code == 1

    # Verify error is printed but no help command suggestion (covers branch 80->83)
    captured = capsys.readouterr()
    assert "Invalid option." in captured.out
    assert "--help" not in captured.out


def test_run_authentication_error_401(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test that 401 errors show helpful authentication hints."""

    def mock_app(*args: object, **kwargs: object) -> None:
        raise APICallError("Invalid bearer token", status_code=401)

    monkeypatch.setattr("orcheo_sdk.cli.main.app", mock_app)

    with pytest.raises(SystemExit) as exc_info:
        run()
    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "Error: Invalid bearer token" in captured.out
    assert "Hint:" in captured.out
    assert "ORCHEO_SERVICE_TOKEN" in captured.out


def test_run_authentication_error_403(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test that 403 errors show helpful permission hints."""

    def mock_app(*args: object, **kwargs: object) -> None:
        raise APICallError("Missing required scopes: workflows:write", status_code=403)

    monkeypatch.setattr("orcheo_sdk.cli.main.app", mock_app)

    with pytest.raises(SystemExit) as exc_info:
        run()
    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "Error: Missing required scopes: workflows:write" in captured.out
    assert "Hint:" in captured.out
    assert "permissions" in captured.out


def test_run_api_error_without_hint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test that non-auth API errors don't show hints."""

    def mock_app(*args: object, **kwargs: object) -> None:
        raise APICallError("Server error", status_code=500)

    monkeypatch.setattr("orcheo_sdk.cli.main.app", mock_app)

    with pytest.raises(SystemExit) as exc_info:
        run()
    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "Error: Server error" in captured.out
    assert "Hint:" not in captured.out
