"""Tests for the CLI config command."""

from __future__ import annotations
import tomllib
from pathlib import Path
from typer.testing import CliRunner
from orcheo_sdk.cli.config import CONFIG_FILENAME
from orcheo_sdk.cli.main import app


def test_config_command_writes_profiles_from_env_file(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "ORCHEO_API_URL=http://env-file.test",
                "ORCHEO_SERVICE_TOKEN=env-token",
                "ORCHEO_CHATKIT_PUBLIC_BASE_URL=http://canvas.test",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["config", "--env-file", str(env_file), "--profile", "default", "-p", "local"],
        env=env,
    )

    assert result.exit_code == 0

    config_path = Path(env["ORCHEO_CONFIG_DIR"]) / CONFIG_FILENAME
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    profiles = data["profiles"]

    for profile_name in ("default", "local"):
        profile = profiles[profile_name]
        assert profile["api_url"] == "http://env-file.test"
        assert profile["service_token"] == "env-token"
        assert profile["chatkit_public_base_url"] == "http://canvas.test"


def test_config_command_uses_environment_defaults(
    runner: CliRunner, env: dict[str, str]
) -> None:
    result = runner.invoke(app, ["config"], env=env)

    assert result.exit_code == 0

    config_path = Path(env["ORCHEO_CONFIG_DIR"]) / CONFIG_FILENAME
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    profile = data["profiles"]["default"]

    assert profile["api_url"] == env["ORCHEO_API_URL"]
    assert profile["service_token"] == env["ORCHEO_SERVICE_TOKEN"]
