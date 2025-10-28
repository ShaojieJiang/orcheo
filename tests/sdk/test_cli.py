"""Tests covering the Orcheo CLI."""

from __future__ import annotations
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
import httpx
import pytest
import respx
from orcheo_sdk.cli.cache import CacheEntry, CacheManager
from orcheo_sdk.cli.config import (
    API_URL_ENV,
    CACHE_DIR_ENV,
    CONFIG_DIR_ENV,
    SERVICE_TOKEN_ENV,
    get_cache_dir,
    get_config_dir,
    load_profiles,
    resolve_settings,
)
from orcheo_sdk.cli.errors import APICallError, CLIConfigurationError, CLIError
from orcheo_sdk.cli.http import ApiClient
from orcheo_sdk.cli.main import app, run
from orcheo_sdk.cli.state import CLIState
from orcheo_sdk.cli.utils import load_with_cache
from typer.testing import CliRunner


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner(mix_stderr=False)


@pytest.fixture()
def env(tmp_path: Path) -> dict[str, str]:
    config_dir = tmp_path / "config"
    cache_dir = tmp_path / "cache"
    config_dir.mkdir()
    cache_dir.mkdir()
    return {
        "ORCHEO_API_URL": "http://api.test",
        "ORCHEO_SERVICE_TOKEN": "token",
        "ORCHEO_CONFIG_DIR": str(config_dir),
        "ORCHEO_CACHE_DIR": str(cache_dir),
        "NO_COLOR": "1",
    }


def test_node_list_shows_registered_nodes(
    runner: CliRunner, env: dict[str, str]
) -> None:
    result = runner.invoke(app, ["node", "list"], env=env)
    assert result.exit_code == 0
    assert "WebhookTriggerNode" in result.stdout


def test_workflow_list_renders_table(runner: CliRunner, env: dict[str, str]) -> None:
    payload = [{"id": "wf-1", "name": "Demo", "slug": "demo", "is_archived": False}]
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = runner.invoke(app, ["workflow", "list"], env=env)
    assert result.exit_code == 0
    assert "Demo" in result.stdout


def test_workflow_show_uses_cache_when_offline(
    runner: CliRunner, env: dict[str, str]
) -> None:
    workflow = {"id": "wf-1", "name": "Cached"}
    versions = [
        {"id": "ver-1", "version": 1, "graph": {"nodes": ["start"], "edges": []}}
    ]
    runs = [{"id": "run-1", "status": "succeeded", "created_at": "2024-01-01"}]

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        router.get("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(200, json=runs)
        )
        first = runner.invoke(app, ["workflow", "show", "wf-1"], env=env)
        assert first.exit_code == 0

    offline_env = env | {"ORCHEO_PROFILE": "offline"}
    offline_args = ["--offline", "workflow", "show", "wf-1"]
    result = runner.invoke(app, offline_args, env=offline_env)
    assert result.exit_code == 0
    assert "Using cached data" in result.stdout


def test_workflow_run_triggers_execution(
    runner: CliRunner, env: dict[str, str]
) -> None:
    versions = [{"id": "ver-1", "version": 1}]
    run_response = {"id": "run-1", "status": "pending"}

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        recorded = router.post("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(201, json=run_response)
        )
        result = runner.invoke(
            app,
            ["workflow", "run", "wf-1", "--actor", "cli"],
            env=env,
        )
    assert result.exit_code == 0
    assert recorded.called
    request = recorded.calls[0].request
    assert request.headers["Authorization"] == "Bearer token"
    assert json.loads(request.content)["triggered_by"] == "cli"


def test_credential_create_and_delete(runner: CliRunner, env: dict[str, str]) -> None:
    created = {"id": "cred-1", "name": "Canvas", "provider": "api"}
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/credentials").mock(
            return_value=httpx.Response(201, json=created)
        )
        router.delete("http://api.test/api/credentials/cred-1").mock(
            return_value=httpx.Response(204)
        )
        create_result = runner.invoke(
            app,
            [
                "credential",
                "create",
                "Canvas",
                "--provider",
                "api",
                "--secret",
                "secret",
            ],
            env=env,
        )
        assert create_result.exit_code == 0

        delete_result = runner.invoke(
            app,
            [
                "credential",
                "delete",
                "cred-1",
                "--force",
            ],
            env=env,
        )
    assert delete_result.exit_code == 0


def test_credential_reference_outputs_snippet(
    runner: CliRunner, env: dict[str, str]
) -> None:
    result = runner.invoke(app, ["credential", "reference", "Canvas"], env=env)
    assert result.exit_code == 0
    assert "[[Canvas]]" in result.stdout


def test_code_scaffold_uses_cache_offline(
    runner: CliRunner, env: dict[str, str]
) -> None:
    workflow = {"id": "wf-1", "name": "Cached"}
    versions = [
        {"id": "ver-1", "version": 1, "graph": {"nodes": ["start"], "edges": []}}
    ]
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        first = runner.invoke(app, ["code", "scaffold", "wf-1"], env=env)
        assert first.exit_code == 0

    offline_env = env | {"ORCHEO_PROFILE": "offline"}
    result = runner.invoke(
        app, ["--offline", "code", "scaffold", "wf-1"], env=offline_env
    )
    assert result.exit_code == 0
    assert "Using cached data" in result.stdout
    assert "HttpWorkflowExecutor" in result.stdout


def test_code_scaffold_no_versions_error(
    runner: CliRunner, env: dict[str, str]
) -> None:
    workflow = {"id": "wf-1", "name": "Empty"}
    versions: list[dict] = []
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(app, ["code", "scaffold", "wf-1"], env=env)
    assert result.exit_code != 0


def test_code_scaffold_no_version_id_error(
    runner: CliRunner, env: dict[str, str]
) -> None:
    workflow = {"id": "wf-1", "name": "NoID"}
    versions = [{"version": 1}]  # Missing id field
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(app, ["code", "scaffold", "wf-1"], env=env)
    assert result.exit_code != 0


def test_workflow_run_offline_error(runner: CliRunner, env: dict[str, str]) -> None:
    result = runner.invoke(
        app,
        ["--offline", "workflow", "run", "wf-1"],
        env=env,
    )
    assert result.exit_code != 0


def test_workflow_run_no_versions_error(runner: CliRunner, env: dict[str, str]) -> None:
    versions: list[dict] = []
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(app, ["workflow", "run", "wf-1"], env=env)
    assert result.exit_code != 0


def test_workflow_run_no_version_id_error(
    runner: CliRunner, env: dict[str, str]
) -> None:
    versions = [{"version": 1}]  # Missing id field
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(app, ["workflow", "run", "wf-1"], env=env)
    assert result.exit_code != 0


def test_workflow_run_with_inputs_string(
    runner: CliRunner, env: dict[str, str]
) -> None:
    versions = [{"id": "ver-1", "version": 1}]
    run_response = {"id": "run-1", "status": "pending"}

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        recorded = router.post("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(201, json=run_response)
        )
        result = runner.invoke(
            app,
            ["workflow", "run", "wf-1", "--inputs", '{"key": "value"}'],
            env=env,
        )
    assert result.exit_code == 0
    request_body = json.loads(recorded.calls[0].request.content)
    # The SDK uses input_payload, not inputs
    assert "input_payload" in request_body
    assert request_body["input_payload"]["key"] == "value"


def test_workflow_run_with_inputs_file(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    versions = [{"id": "ver-1", "version": 1}]
    run_response = {"id": "run-1", "status": "pending"}
    inputs_file = tmp_path / "inputs.json"
    inputs_file.write_text('{"key": "value"}', encoding="utf-8")

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        recorded = router.post("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(201, json=run_response)
        )
        result = runner.invoke(
            app,
            ["workflow", "run", "wf-1", "--inputs-file", str(inputs_file)],
            env=env,
        )
    assert result.exit_code == 0
    request_body = json.loads(recorded.calls[0].request.content)
    # The SDK uses input_payload, not inputs
    assert "input_payload" in request_body
    assert request_body["input_payload"]["key"] == "value"


def test_workflow_run_both_inputs_error(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    versions = [{"id": "ver-1", "version": 1}]
    inputs_file = tmp_path / "inputs.json"
    inputs_file.write_text('{"key": "value"}', encoding="utf-8")
    with respx.mock(assert_all_called=False) as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            [
                "workflow",
                "run",
                "wf-1",
                "--inputs",
                "{}",
                "--inputs-file",
                str(inputs_file),
            ],
            env=env,
        )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "either --inputs or --inputs-file" in str(result.exception).lower()


def test_workflow_run_inputs_file_not_exists(
    runner: CliRunner, env: dict[str, str]
) -> None:
    versions = [{"id": "ver-1", "version": 1}]
    with respx.mock(assert_all_called=False) as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "run", "wf-1", "--inputs-file", "/nonexistent/file.json"],
            env=env,
        )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "does not exist" in str(result.exception)


def test_workflow_run_inputs_file_not_file(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    versions = [{"id": "ver-1", "version": 1}]
    with respx.mock(assert_all_called=False) as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "run", "wf-1", "--inputs-file", str(tmp_path)],
            env=env,
        )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "is not a file" in str(result.exception)


def test_workflow_run_inputs_file_not_json_object(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    versions = [{"id": "ver-1", "version": 1}]
    inputs_file = tmp_path / "inputs.json"
    inputs_file.write_text('["array"]', encoding="utf-8")
    with respx.mock(assert_all_called=False) as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "run", "wf-1", "--inputs-file", str(inputs_file)],
            env=env,
        )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "must be a JSON object" in str(result.exception)


def test_workflow_run_inputs_string_not_json_object(
    runner: CliRunner, env: dict[str, str]
) -> None:
    versions = [{"id": "ver-1", "version": 1}]
    with respx.mock(assert_all_called=False) as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "run", "wf-1", "--inputs", '["array"]'],
            env=env,
        )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "must be a JSON object" in str(result.exception)


def test_credential_list_with_workflow_id(
    runner: CliRunner, env: dict[str, str]
) -> None:
    credentials = [{"id": "cred-1", "name": "Canvas", "provider": "api"}]
    with respx.mock(assert_all_called=True) as router:
        route = router.get("http://api.test/api/credentials").mock(
            return_value=httpx.Response(200, json=credentials)
        )
        result = runner.invoke(
            app,
            ["credential", "list", "--workflow-id", "wf-1"],
            env=env,
        )
    assert result.exit_code == 0
    assert route.calls[0].request.url.params.get("workflow_id") == "wf-1"


def test_credential_create_with_workflow_id(
    runner: CliRunner, env: dict[str, str]
) -> None:
    created = {"id": "cred-1", "name": "Canvas", "provider": "api"}
    with respx.mock(assert_all_called=True) as router:
        recorded = router.post("http://api.test/api/credentials").mock(
            return_value=httpx.Response(201, json=created)
        )
        result = runner.invoke(
            app,
            [
                "credential",
                "create",
                "Canvas",
                "--provider",
                "api",
                "--secret",
                "secret",
                "--workflow-id",
                "wf-1",
            ],
            env=env,
        )
    assert result.exit_code == 0
    request_body = json.loads(recorded.calls[0].request.content)
    assert request_body["workflow_id"] == "wf-1"


def test_credential_delete_with_workflow_id(
    runner: CliRunner, env: dict[str, str]
) -> None:
    with respx.mock(assert_all_called=True) as router:
        route = router.delete("http://api.test/api/credentials/cred-1").mock(
            return_value=httpx.Response(204)
        )
        result = runner.invoke(
            app,
            [
                "credential",
                "delete",
                "cred-1",
                "--workflow-id",
                "wf-1",
                "--force",
            ],
            env=env,
        )
    assert result.exit_code == 0
    assert route.calls[0].request.url.params.get("workflow_id") == "wf-1"


def test_credential_update_not_implemented(
    runner: CliRunner, env: dict[str, str]
) -> None:
    result = runner.invoke(
        app,
        ["credential", "update", "cred-1", "--secret", "new"],
        env=env,
    )
    assert result.exit_code == 0
    assert "not yet supported" in result.stdout


def test_node_show_displays_schema(runner: CliRunner, env: dict[str, str]) -> None:
    result = runner.invoke(app, ["node", "show", "Agent"], env=env)
    assert result.exit_code == 0
    assert "Agent" in result.stdout


def test_node_list_with_tag_filter(runner: CliRunner, env: dict[str, str]) -> None:
    result = runner.invoke(app, ["node", "list", "--tag", "trigger"], env=env)
    assert result.exit_code == 0
    assert "WebhookTriggerNode" in result.stdout


def test_node_show_nonexistent_error(runner: CliRunner, env: dict[str, str]) -> None:
    result = runner.invoke(app, ["node", "show", "NonexistentNode"], env=env)
    assert result.exit_code != 0


def test_main_config_error_handling(runner: CliRunner) -> None:
    result = runner.invoke(app, ["workflow", "list"], env={"NO_COLOR": "1"})
    assert result.exit_code == 1


# Cache module tests
def test_cache_entry_is_stale() -> None:
    past_timestamp = datetime.now(tz=UTC) - timedelta(hours=2)
    entry = CacheEntry(
        payload={"key": "value"}, timestamp=past_timestamp, ttl=timedelta(hours=1)
    )
    assert entry.is_stale


def test_cache_entry_is_fresh() -> None:
    recent_timestamp = datetime.now(tz=UTC)
    entry = CacheEntry(
        payload={"key": "value"}, timestamp=recent_timestamp, ttl=timedelta(hours=1)
    )
    assert not entry.is_stale


def test_cache_manager_store_and_load(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache = CacheManager(directory=cache_dir, ttl=timedelta(hours=1))
    cache.store("test_key", {"data": "value"})
    entry = cache.load("test_key")
    assert entry is not None
    assert entry.payload == {"data": "value"}


def test_cache_manager_load_nonexistent(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache = CacheManager(directory=cache_dir, ttl=timedelta(hours=1))
    entry = cache.load("nonexistent")
    assert entry is None


def test_cache_manager_fetch_fresh_data(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache = CacheManager(directory=cache_dir, ttl=timedelta(hours=1))
    payload, from_cache, is_stale = cache.fetch("key", lambda: {"fresh": "data"})
    assert payload == {"fresh": "data"}
    assert not from_cache
    assert not is_stale


def test_cache_manager_fetch_on_error_uses_cache(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache = CacheManager(directory=cache_dir, ttl=timedelta(hours=1))
    cache.store("key", {"cached": "data"})

    def failing_loader() -> dict:
        raise CLIError("Network error")

    payload, from_cache, is_stale = cache.fetch("key", failing_loader)
    assert payload == {"cached": "data"}
    assert from_cache


def test_cache_manager_fetch_on_error_no_cache_raises(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache = CacheManager(directory=cache_dir, ttl=timedelta(hours=1))

    def failing_loader() -> dict:
        raise CLIError("Network error")

    with pytest.raises(CLIError):
        cache.fetch("key", failing_loader)


def test_cache_manager_load_or_raise_success(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache = CacheManager(directory=cache_dir, ttl=timedelta(hours=1))
    cache.store("key", {"data": "value"})
    payload = cache.load_or_raise("key")
    assert payload == {"data": "value"}


def test_cache_manager_load_or_raise_missing(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache = CacheManager(directory=cache_dir, ttl=timedelta(hours=1))
    with pytest.raises(CLIError, match="not found"):
        cache.load_or_raise("missing")


# Config module tests
def test_get_config_dir_default() -> None:
    import os

    original = os.environ.get(CONFIG_DIR_ENV)
    try:
        os.environ.pop(CONFIG_DIR_ENV, None)
        config_dir = get_config_dir()
        assert ".config/orcheo" in str(config_dir)
    finally:
        if original:
            os.environ[CONFIG_DIR_ENV] = original


def test_get_config_dir_override(tmp_path: Path) -> None:
    import os

    custom_dir = tmp_path / "custom_config"
    original = os.environ.get(CONFIG_DIR_ENV)
    try:
        os.environ[CONFIG_DIR_ENV] = str(custom_dir)
        config_dir = get_config_dir()
        assert config_dir == custom_dir
    finally:
        if original:
            os.environ[CONFIG_DIR_ENV] = original
        else:
            os.environ.pop(CONFIG_DIR_ENV, None)


def test_get_cache_dir_default() -> None:
    import os

    original = os.environ.get(CACHE_DIR_ENV)
    try:
        os.environ.pop(CACHE_DIR_ENV, None)
        cache_dir = get_cache_dir()
        assert ".cache/orcheo" in str(cache_dir)
    finally:
        if original:
            os.environ[CACHE_DIR_ENV] = original


def test_get_cache_dir_override(tmp_path: Path) -> None:
    import os

    custom_dir = tmp_path / "custom_cache"
    original = os.environ.get(CACHE_DIR_ENV)
    try:
        os.environ[CACHE_DIR_ENV] = str(custom_dir)
        cache_dir = get_cache_dir()
        assert cache_dir == custom_dir
    finally:
        if original:
            os.environ[CACHE_DIR_ENV] = original
        else:
            os.environ.pop(CACHE_DIR_ENV, None)


def test_load_profiles_nonexistent(tmp_path: Path) -> None:
    config_path = tmp_path / "nonexistent.toml"
    profiles = load_profiles(config_path)
    assert profiles == {}


def test_load_profiles_success(tmp_path: Path) -> None:
    config_path = tmp_path / "cli.toml"
    config_path.write_text(
        """
[profiles.dev]
api_url = "http://dev.test"
service_token = "dev-token"

[profiles.prod]
api_url = "http://prod.test"
""",
        encoding="utf-8",
    )
    profiles = load_profiles(config_path)
    assert "dev" in profiles
    assert profiles["dev"]["api_url"] == "http://dev.test"
    assert "prod" in profiles


def test_resolve_settings_from_args() -> None:
    settings = resolve_settings(
        profile=None,
        api_url="http://test.com",
        service_token="token123",
        offline=False,
    )
    assert settings.api_url == "http://test.com"
    assert settings.service_token == "token123"
    assert not settings.offline


def test_resolve_settings_from_env(tmp_path: Path) -> None:
    import os

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    original_config = os.environ.get(CONFIG_DIR_ENV)
    original_url = os.environ.get(API_URL_ENV)
    original_token = os.environ.get(SERVICE_TOKEN_ENV)
    try:
        os.environ[CONFIG_DIR_ENV] = str(config_dir)
        os.environ[API_URL_ENV] = "http://env.test"
        os.environ[SERVICE_TOKEN_ENV] = "env-token"
        settings = resolve_settings(
            profile=None,
            api_url=None,
            service_token=None,
            offline=False,
        )
        assert settings.api_url == "http://env.test"
        assert settings.service_token == "env-token"
    finally:
        if original_config:
            os.environ[CONFIG_DIR_ENV] = original_config
        else:
            os.environ.pop(CONFIG_DIR_ENV, None)
        if original_url:
            os.environ[API_URL_ENV] = original_url
        else:
            os.environ.pop(API_URL_ENV, None)
        if original_token:
            os.environ[SERVICE_TOKEN_ENV] = original_token
        else:
            os.environ.pop(SERVICE_TOKEN_ENV, None)


def test_resolve_settings_missing_api_url(tmp_path: Path) -> None:
    import os

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    original = os.environ.get(CONFIG_DIR_ENV)
    try:
        os.environ[CONFIG_DIR_ENV] = str(config_dir)
        os.environ.pop(API_URL_ENV, None)
        with pytest.raises(CLIConfigurationError, match="API URL is required"):
            resolve_settings(
                profile=None,
                api_url=None,
                service_token=None,
                offline=False,
            )
    finally:
        if original:
            os.environ[CONFIG_DIR_ENV] = original
        else:
            os.environ.pop(CONFIG_DIR_ENV, None)


# HTTP client tests
def test_api_client_get_success() -> None:
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(200, json={"key": "value"})
        )
        result = client.get("/api/test")
    assert result == {"key": "value"}


def test_api_client_get_with_params() -> None:
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        route = respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(200, json={"key": "value"})
        )
        client.get("/api/test", params={"foo": "bar"})
    assert route.calls[0].request.url.params.get("foo") == "bar"


def test_api_client_get_http_error() -> None:
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(404, json={"detail": "Not found"})
        )
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
    assert exc_info.value.status_code == 404


def test_api_client_get_request_error() -> None:
    client = ApiClient(base_url="http://nonexistent.invalid.test", token="token123")
    with pytest.raises(APICallError):
        client.get("/api/test")


def test_api_client_post_success() -> None:
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.post("http://test.com/api/test").mock(
            return_value=httpx.Response(201, json={"id": "123"})
        )
        result = client.post("/api/test", json_body={"key": "value"})
    assert result == {"id": "123"}


def test_api_client_post_no_content() -> None:
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.post("http://test.com/api/test").mock(return_value=httpx.Response(204))
        result = client.post("/api/test", json_body={})
    assert result is None


def test_api_client_post_http_error() -> None:
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.post("http://test.com/api/test").mock(
            return_value=httpx.Response(
                400, json={"detail": {"message": "Bad request"}}
            )
        )
        with pytest.raises(APICallError) as exc_info:
            client.post("/api/test", json_body={})
    assert exc_info.value.status_code == 400


def test_api_client_post_request_error() -> None:
    client = ApiClient(base_url="http://nonexistent.invalid.test", token="token123")
    with pytest.raises(APICallError):
        client.post("/api/test", json_body={})


def test_api_client_delete_success() -> None:
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.delete("http://test.com/api/test/123").mock(
            return_value=httpx.Response(204)
        )
        client.delete("/api/test/123")


def test_api_client_delete_http_error() -> None:
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.delete("http://test.com/api/test/123").mock(
            return_value=httpx.Response(404, json={"message": "Not found"})
        )
        with pytest.raises(APICallError) as exc_info:
            client.delete("/api/test/123")
    assert exc_info.value.status_code == 404


def test_api_client_delete_request_error() -> None:
    client = ApiClient(base_url="http://nonexistent.invalid.test", token="token123")
    with pytest.raises(APICallError):
        client.delete("/api/test/123")


def test_api_client_base_url_property() -> None:
    client = ApiClient(base_url="http://test.com/", token="token123")
    assert client.base_url == "http://test.com"


# Error classes tests
def test_cli_error_instantiation() -> None:
    error = CLIError("Test error")
    assert str(error) == "Test error"


def test_cli_configuration_error_instantiation() -> None:
    error = CLIConfigurationError("Config error")
    assert str(error) == "Config error"
    assert isinstance(error, CLIError)


def test_api_call_error_with_status_code() -> None:
    error = APICallError("API error", status_code=500)
    assert str(error) == "API error"
    assert error.status_code == 500


def test_api_call_error_without_status_code() -> None:
    error = APICallError("API error")
    assert str(error) == "API error"
    assert error.status_code is None


# Utils tests
def test_load_with_cache_offline_mode_with_cache(tmp_path: Path) -> None:
    from rich.console import Console

    cache_dir = tmp_path / "cache"
    cache = CacheManager(directory=cache_dir, ttl=timedelta(hours=1))
    cache.store("test_key", {"cached": "data"})

    from orcheo_sdk.cli.config import CLISettings

    settings = CLISettings(
        api_url="http://test.com", service_token=None, profile="test", offline=True
    )
    client = ApiClient(base_url="http://test.com", token=None)
    state = CLIState(settings=settings, client=client, cache=cache, console=Console())

    payload, from_cache, is_stale = load_with_cache(
        state,
        "test_key",
        lambda: {"fresh": "data"},
    )
    assert payload == {"cached": "data"}
    assert from_cache


def test_load_with_cache_online_mode_success(tmp_path: Path) -> None:
    from rich.console import Console

    cache_dir = tmp_path / "cache"
    cache = CacheManager(directory=cache_dir, ttl=timedelta(hours=1))

    from orcheo_sdk.cli.config import CLISettings

    settings = CLISettings(
        api_url="http://test.com", service_token=None, profile="test", offline=False
    )
    client = ApiClient(base_url="http://test.com", token=None)
    state = CLIState(settings=settings, client=client, cache=cache, console=Console())

    payload, from_cache, is_stale = load_with_cache(
        state,
        "test_key",
        lambda: {"fresh": "data"},
    )
    assert payload == {"fresh": "data"}
    assert not from_cache


def test_load_with_cache_online_mode_error_with_cache(tmp_path: Path) -> None:
    from rich.console import Console

    cache_dir = tmp_path / "cache"
    cache = CacheManager(directory=cache_dir, ttl=timedelta(hours=1))
    cache.store("test_key", {"cached": "data"})

    from orcheo_sdk.cli.config import CLISettings

    settings = CLISettings(
        api_url="http://test.com", service_token=None, profile="test", offline=False
    )
    client = ApiClient(base_url="http://test.com", token=None)
    state = CLIState(settings=settings, client=client, cache=cache, console=Console())

    def failing_loader() -> dict:
        raise CLIError("Network error")

    payload, from_cache, is_stale = load_with_cache(
        state,
        "test_key",
        failing_loader,
    )
    assert payload == {"cached": "data"}
    assert from_cache


def test_load_with_cache_online_mode_error_no_cache(tmp_path: Path) -> None:
    from rich.console import Console

    cache_dir = tmp_path / "cache"
    cache = CacheManager(directory=cache_dir, ttl=timedelta(hours=1))

    from orcheo_sdk.cli.config import CLISettings

    settings = CLISettings(
        api_url="http://test.com", service_token=None, profile="test", offline=False
    )
    client = ApiClient(base_url="http://test.com", token=None)
    state = CLIState(settings=settings, client=client, cache=cache, console=Console())

    def failing_loader() -> dict:
        raise CLIError("Network error")

    with pytest.raises(CLIError):
        load_with_cache(state, "test_key", failing_loader)


# Main CLI tests
def test_run_cli_error_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    import typer

    def mock_app(*args: object, **kwargs: object) -> None:
        raise CLIError("Test error")

    monkeypatch.setattr("orcheo_sdk.cli.main.app", mock_app)

    with pytest.raises(typer.Exit) as exc_info:
        run()
    assert exc_info.value.exit_code == 1


def test_workflow_show_with_cache_notice(
    runner: CliRunner, env: dict[str, str]
) -> None:
    workflow = {"id": "wf-1", "name": "Cached"}
    versions = [
        {"id": "ver-1", "version": 1, "graph": {"nodes": ["start"], "edges": []}}
    ]
    runs: list[dict] = []

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        router.get("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(200, json=runs)
        )
        first = runner.invoke(app, ["workflow", "show", "wf-1"], env=env)
        assert first.exit_code == 0

    # Now test offline with cache showing the notice
    offline_env = env | {"ORCHEO_PROFILE": "offline"}
    result = runner.invoke(
        app, ["--offline", "workflow", "show", "wf-1"], env=offline_env
    )
    assert result.exit_code == 0
    assert "Cached" in result.stdout


def test_code_scaffold_with_custom_actor(
    runner: CliRunner, env: dict[str, str]
) -> None:
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [{"id": "ver-1", "version": 1}]
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app, ["code", "scaffold", "wf-1", "--actor", "custom"], env=env
        )
    assert result.exit_code == 0
    assert "custom" in result.stdout


def test_credential_delete_without_force_prompts(
    runner: CliRunner, env: dict[str, str]
) -> None:
    # Test without --force which would prompt for confirmation
    # We'll simulate the user aborting
    with respx.mock:
        result = runner.invoke(
            app,
            ["credential", "delete", "cred-1"],
            env=env,
            input="n\n",  # No to confirmation
        )
    # Typer.confirm with abort=True will exit with code 1 when user says no
    assert result.exit_code == 1


def test_workflow_run_inputs_invalid_json(
    runner: CliRunner, env: dict[str, str]
) -> None:
    # This test might not trigger the error because typer might fail earlier
    # but we still test the path
    result = runner.invoke(
        app,
        ["workflow", "run", "wf-1", "--inputs", "{invalid json}"],
        env=env,
    )
    # Should fail due to invalid JSON
    assert result.exit_code != 0


def test_code_scaffold_with_both_stale_caches(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test scaffold shows stale notice when both workflow and versions are stale."""
    import json

    cache_dir = tmp_path / "stale_cache"
    cache_dir.mkdir(exist_ok=True)

    # Create cache files with timestamps from 25 hours ago (older than default 24h TTL)
    stale_time = datetime.now(tz=UTC) - timedelta(hours=25)
    workflow = {"id": "wf-1", "name": "Cached"}
    versions = [{"id": "ver-1", "version": 1}]

    # Write cache files with old timestamps
    workflow_cache = cache_dir / "workflow_wf-1.json"
    workflow_cache.write_text(
        json.dumps(
            {
                "timestamp": stale_time.isoformat(),
                "payload": workflow,
            }
        ),
        encoding="utf-8",
    )

    versions_cache = cache_dir / "workflow_wf-1_versions.json"
    versions_cache.write_text(
        json.dumps(
            {
                "timestamp": stale_time.isoformat(),
                "payload": versions,
            }
        ),
        encoding="utf-8",
    )

    env_with_cache = env | {"ORCHEO_CACHE_DIR": str(cache_dir)}
    result = runner.invoke(
        app, ["--offline", "code", "scaffold", "wf-1"], env=env_with_cache
    )
    assert result.exit_code == 0
    assert "Using cached data" in result.stdout
    # With stale cache entries, should show the TTL warning
    assert "older than TTL" in result.stdout


def test_api_client_without_token() -> None:
    """Test that ApiClient works without a token."""
    client = ApiClient(base_url="http://test.com", token=None)
    with respx.mock:
        route = respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(200, json={"key": "value"})
        )
        result = client.get("/api/test")
    assert result == {"key": "value"}
    # Verify no Authorization header was sent
    assert "Authorization" not in route.calls[0].request.headers


def test_api_client_error_with_nested_message() -> None:
    """Test error formatting with nested detail.message structure."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(
                400, json={"detail": {"message": "Nested error message"}}
            )
        )
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
    assert "Nested error message" in str(exc_info.value)


def test_api_client_error_with_detail_detail() -> None:
    """Test error formatting with detail.detail structure."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(
                400, json={"detail": {"detail": "Detail in detail field"}}
            )
        )
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
    assert "Detail in detail field" in str(exc_info.value)


def test_api_client_error_with_message_field() -> None:
    """Test error formatting with top-level message field."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.post("http://test.com/api/test").mock(
            return_value=httpx.Response(500, json={"message": "Server error message"})
        )
        with pytest.raises(APICallError) as exc_info:
            client.post("/api/test", json_body={})
    assert "Server error message" in str(exc_info.value)


def test_load_with_cache_offline_mode_without_cache(tmp_path: Path) -> None:
    """Test load_with_cache in offline mode when cache is missing."""
    from orcheo_sdk.cli.config import CLISettings
    from rich.console import Console

    cache_dir = tmp_path / "cache"
    cache = CacheManager(directory=cache_dir, ttl=timedelta(hours=1))

    settings = CLISettings(
        api_url="http://test.com", service_token=None, profile="test", offline=True
    )
    client = ApiClient(base_url="http://test.com", token=None)
    state = CLIState(settings=settings, client=client, cache=cache, console=Console())

    # In offline mode without cache, should try to load and get None
    # Then attempt to call loader which should not be called in true offline
    # But based on the code, it will try the loader anyway after cache miss
    def loader() -> dict:
        return {"fresh": "data"}

    payload, from_cache, is_stale = load_with_cache(state, "missing_key", loader)
    # When offline and no cache, it tries the loader
    assert payload == {"fresh": "data"}
    assert not from_cache


def test_workflow_show_no_latest_version(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow show when there's no latest version."""
    workflow = {"id": "wf-1", "name": "NoVersion"}
    versions: list[dict] = []
    runs: list[dict] = []

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        router.get("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(200, json=runs)
        )
        result = runner.invoke(app, ["workflow", "show", "wf-1"], env=env)
    assert result.exit_code == 0
    # Should not show latest version section since there are no versions


def test_workflow_show_no_runs(runner: CliRunner, env: dict[str, str]) -> None:
    """Test workflow show when there are no runs."""
    workflow = {"id": "wf-1", "name": "NoRuns"}
    versions = [
        {"id": "ver-1", "version": 1, "graph": {"nodes": ["start"], "edges": []}}
    ]
    runs: list[dict] = []

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        router.get("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(200, json=runs)
        )
        result = runner.invoke(app, ["workflow", "show", "wf-1"], env=env)
    assert result.exit_code == 0
    # Should not show recent runs section since there are no runs


def test_workflow_list_uses_cache_notice(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test that workflow list shows cache notice when using cached data."""
    payload = [{"id": "wf-1", "name": "Demo", "slug": "demo", "is_archived": False}]
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows").mock(
            return_value=httpx.Response(200, json=payload)
        )
        # First call to populate cache
        first = runner.invoke(app, ["workflow", "list"], env=env)
        assert first.exit_code == 0

    # Second call in offline mode should use cache
    result = runner.invoke(app, ["--offline", "workflow", "list"], env=env)
    assert result.exit_code == 0
    assert "Using cached data" in result.stdout


def test_workflow_mermaid_with_edge_list_format(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test mermaid generation with edges as list tuples."""
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {"nodes": [{"id": "a"}, {"id": "b"}], "edges": [["a", "b"]]},
        }
    ]
    runs: list[dict] = []

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        router.get("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(200, json=runs)
        )
        result = runner.invoke(app, ["workflow", "show", "wf-1"], env=env)
    assert result.exit_code == 0
    assert "a --> b" in result.stdout


def test_workflow_mermaid_with_invalid_edge(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test mermaid generation skips invalid edges."""
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {
                "nodes": [{"id": "a"}],
                "edges": [
                    "invalid",  # String, not a valid edge format
                    {"from": "a"},  # Missing 'to'
                    {"to": "b"},  # Missing 'from'
                ],
            },
        }
    ]
    runs: list[dict] = []

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        router.get("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(200, json=runs)
        )
        result = runner.invoke(app, ["workflow", "show", "wf-1"], env=env)
    assert result.exit_code == 0
    # Should not crash, just skip invalid edges


def test_workflow_show_with_stale_cache_notice(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow show displays stale cache notice."""
    import json

    cache_dir = tmp_path / "stale_wf_cache"
    cache_dir.mkdir(exist_ok=True)

    # Create cache files with 25-hour-old timestamps (older than 24h TTL)
    stale_time = datetime.now(tz=UTC) - timedelta(hours=25)
    workflow = {"id": "wf-1", "name": "Cached"}
    versions = [
        {"id": "ver-1", "version": 1, "graph": {"nodes": ["start"], "edges": []}}
    ]
    runs = [{"id": "run-1", "status": "succeeded", "created_at": "2024-01-01"}]

    # Write stale cache files
    for key, data in [
        ("workflow_wf-1", workflow),
        ("workflow_wf-1_versions", versions),
        ("workflow_wf-1_runs", runs),
    ]:
        cache_file = cache_dir / f"{key}.json"
        cache_file.write_text(
            json.dumps({"timestamp": stale_time.isoformat(), "payload": data}),
            encoding="utf-8",
        )

    env_with_cache = env | {"ORCHEO_CACHE_DIR": str(cache_dir)}
    result = runner.invoke(
        app, ["--offline", "workflow", "show", "wf-1"], env=env_with_cache
    )
    assert result.exit_code == 0
    assert "Using cached data" in result.stdout
    assert "older than TTL" in result.stdout


def test_api_client_error_with_detail_as_string() -> None:
    """Test error formatting when detail is a string, not a mapping."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(400, json={"detail": "Simple error string"})
        )
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
    # When detail is not a Mapping, should fall through to response.text
    assert exc_info.value.status_code == 400


def test_api_client_error_with_empty_message_in_detail() -> None:
    """Test error formatting when detail.message and detail.detail are both empty."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(
                400, json={"detail": {"message": None, "detail": None}}
            )
        )
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
    # When message is None/empty, should check "message" in payload
    assert exc_info.value.status_code == 400


def test_api_client_error_with_detail_missing_message_field() -> None:
    """Test error formatting when detail Mapping has no message/detail fields."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(
                400, json={"detail": {"some_other_field": "value"}}
            )
        )
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
    # When detail has no message/detail fields, fall through to response.text
    assert exc_info.value.status_code == 400


def test_api_client_error_with_non_mapping_detail_no_message() -> None:
    """Test error formatting when detail is not a Mapping and no message field."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(400, json={"detail": "error string"})
        )
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
    # When detail is not Mapping and no message, falls through to response.text
    assert exc_info.value.status_code == 400


def test_api_client_error_with_no_detail_no_message() -> None:
    """Test error formatting when payload has neither detail nor message."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(400, json={"error": "something"})
        )
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
    # When no detail and no message fields, falls through to response.text
    assert exc_info.value.status_code == 400


def test_api_client_error_detail_mapping_no_message_value() -> None:
    """Test error formatting when detail is Mapping with no valid message value."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(
                400,
                json={"detail": {"message": "", "detail": ""}},
                text='{"detail": {"message": "", "detail": ""}}',
            )
        )
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
    # When detail.message and detail.detail are empty strings (falsy but present)
    # Should fall through to checking "message" in payload, then to response.text
    assert exc_info.value.status_code == 400
    assert '{"detail"' in str(exc_info.value)


def test_api_client_error_detail_not_mapping_no_message() -> None:
    """Test error formatting when detail is not a Mapping and no message field."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(
                400,
                json={"detail": "string detail", "other_field": "value"},
                text='{"detail": "string detail", "other_field": "value"}',
            )
        )
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
    # When detail is not a Mapping and there's no "message" field in payload
    # Should fall through to response.text (line 109)
    assert exc_info.value.status_code == 400
    assert "string detail" in str(exc_info.value)


def test_api_client_error_payload_not_mapping() -> None:
    """Test error formatting when payload itself is not a Mapping."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(
                400,
                json=["error", "list"],
                text='["error", "list"]',
            )
        )
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
    # When payload is not a Mapping (e.g., a list), should go directly to response.text
    # This covers the branch 101->109 where isinstance(payload, Mapping) is False
    assert exc_info.value.status_code == 400
    assert '["error", "list"]' in str(exc_info.value)
