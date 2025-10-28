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
    inputs_file = tmp_path / "inputs.json"
    inputs_file.write_text('{"key": "value"}', encoding="utf-8")
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


def test_workflow_run_inputs_file_not_exists(
    runner: CliRunner, env: dict[str, str]
) -> None:
    result = runner.invoke(
        app,
        ["workflow", "run", "wf-1", "--inputs-file", "/nonexistent/file.json"],
        env=env,
    )
    assert result.exit_code != 0


def test_workflow_run_inputs_file_not_file(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    result = runner.invoke(
        app,
        ["workflow", "run", "wf-1", "--inputs-file", str(tmp_path)],
        env=env,
    )
    assert result.exit_code != 0


def test_workflow_run_inputs_file_not_json_object(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    inputs_file = tmp_path / "inputs.json"
    inputs_file.write_text('["array"]', encoding="utf-8")
    result = runner.invoke(
        app,
        ["workflow", "run", "wf-1", "--inputs-file", str(inputs_file)],
        env=env,
    )
    assert result.exit_code != 0


def test_workflow_run_inputs_string_not_json_object(
    runner: CliRunner, env: dict[str, str]
) -> None:
    result = runner.invoke(
        app,
        ["workflow", "run", "wf-1", "--inputs", '["array"]'],
        env=env,
    )
    assert result.exit_code != 0


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
