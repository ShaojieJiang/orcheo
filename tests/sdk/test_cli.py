"""Tests covering the Orcheo CLI."""

from __future__ import annotations
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
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
    return CliRunner()


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


def test_workflow_list_excludes_archived_by_default(
    runner: CliRunner, env: dict[str, str]
) -> None:
    payload = [{"id": "wf-1", "name": "Active", "slug": "active", "is_archived": False}]
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = runner.invoke(app, ["workflow", "list"], env=env)
    assert result.exit_code == 0
    assert "Active" in result.stdout


def test_workflow_list_includes_archived_with_flag(
    runner: CliRunner, env: dict[str, str]
) -> None:
    payload = [
        {"id": "wf-1", "name": "Active", "slug": "active", "is_archived": False},
        {"id": "wf-2", "name": "Archived", "slug": "archived", "is_archived": True},
    ]
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows?include_archived=true").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = runner.invoke(app, ["workflow", "list", "--archived"], env=env)
    assert result.exit_code == 0
    assert "Active" in result.stdout
    assert "Archived" in result.stdout


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


def test_workflow_delete_with_force(runner: CliRunner, env: dict[str, str]) -> None:
    with respx.mock(assert_all_called=True) as router:
        router.delete("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(204)
        )
        result = runner.invoke(
            app,
            ["workflow", "delete", "wf-1", "--force"],
            env=env,
        )
    assert result.exit_code == 0
    assert "deleted successfully" in result.stdout


def test_workflow_delete_without_force_prompts(
    runner: CliRunner, env: dict[str, str]
) -> None:
    # Test without --force which would prompt for confirmation
    # We'll simulate the user aborting
    with respx.mock:
        result = runner.invoke(
            app,
            ["workflow", "delete", "wf-1"],
            env=env,
            input="n\n",  # No to confirmation
        )
    # Typer.confirm with abort=True will exit with code 1 when user says no
    assert result.exit_code == 1


def test_workflow_delete_with_confirmation(
    runner: CliRunner, env: dict[str, str]
) -> None:
    # Test that delete succeeds when user confirms
    with respx.mock(assert_all_called=True) as router:
        router.delete("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(204)
        )
        result = runner.invoke(
            app,
            ["workflow", "delete", "wf-1"],
            env=env,
            input="y\n",  # Yes to confirmation
        )
    assert result.exit_code == 0
    assert "deleted successfully" in result.stdout


def test_workflow_delete_offline_error(runner: CliRunner, env: dict[str, str]) -> None:
    offline_args = ["--offline", "workflow", "delete", "wf-1", "--force"]
    result = runner.invoke(app, offline_args, env=env)
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "network connectivity" in str(result.exception)


def test_workflow_delete_custom_message(runner: CliRunner, env: dict[str, str]) -> None:
    """Workflow delete with message that doesn't include 'deleted successfully'."""
    with respx.mock(assert_all_called=True) as router:
        # Mock delete to return a response (even though it's 204)
        router.delete("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(204)
        )
        result = runner.invoke(
            app,
            ["workflow", "delete", "wf-1", "--force"],
            env=env,
        )
    assert result.exit_code == 0
    # Should show the default message since delete returns no content
    assert "wf-1" in result.stdout


def test_workflow_delete_with_success_message(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Workflow delete when API returns a message containing 'deleted successfully'."""
    success_message = "Workflow 'wf-1' deleted successfully from system"

    with respx.mock(assert_all_called=False) as router:
        # Mock the delete API call to return a 200 with a message
        router.delete("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json={"message": success_message})
        )
        result = runner.invoke(
            app,
            ["workflow", "delete", "wf-1", "--force"],
            env=env,
        )
    assert result.exit_code == 0
    assert success_message in result.stdout


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
    result = runner.invoke(app, ["node", "show", "AgentNode"], env=env)
    assert result.exit_code == 0
    assert "AgentNode" in result.stdout


def test_node_list_with_tag_filter(runner: CliRunner, env: dict[str, str]) -> None:
    result = runner.invoke(app, ["node", "list", "--tag", "trigger"], env=env)
    assert result.exit_code == 0
    assert "WebhookTriggerNode" in result.stdout


def test_node_show_nonexistent_error(runner: CliRunner, env: dict[str, str]) -> None:
    result = runner.invoke(app, ["node", "show", "NonexistentNode"], env=env)
    assert result.exit_code != 0


def test_node_show_no_schema_info(runner: CliRunner, env: dict[str, str]) -> None:
    """Test node show with node that has neither schema nor attributes."""
    from orcheo.nodes.registry import NodeMetadata, registry

    # Register a test node without model_json_schema and without annotations
    test_meta = NodeMetadata(
        name="TestNodeNoInfo",
        description="Test node without schema",
        category="test",
    )

    class TestNodeNoInfo:
        """Node without model_json_schema and no annotations."""

        pass

    # Register the test node
    registry._nodes["TestNodeNoInfo"] = TestNodeNoInfo
    registry._metadata["TestNodeNoInfo"] = test_meta

    try:
        result = runner.invoke(app, ["node", "show", "TestNodeNoInfo"], env=env)
        assert result.exit_code == 0
        assert "TestNodeNoInfo" in result.stdout
        assert "No schema information available" in result.stdout
    finally:
        # Clean up
        registry._nodes.pop("TestNodeNoInfo", None)
        registry._metadata.pop("TestNodeNoInfo", None)


def test_node_show_with_attributes_only(runner: CliRunner, env: dict[str, str]) -> None:
    """Test node show with node that has attributes but no model_json_schema."""
    from orcheo.nodes.registry import NodeMetadata, registry

    # Register a test node with annotations but no model_json_schema
    test_meta = NodeMetadata(
        name="TestNodeWithAttrs",
        description="Test node with attributes",
        category="test",
    )

    class TestNodeWithAttrs:
        """Node with annotations but no model_json_schema."""

        test_attr: str
        count: int

    # Register the test node
    registry._nodes["TestNodeWithAttrs"] = TestNodeWithAttrs
    registry._metadata["TestNodeWithAttrs"] = test_meta

    try:
        result = runner.invoke(app, ["node", "show", "TestNodeWithAttrs"], env=env)
        assert result.exit_code == 0
        assert "TestNodeWithAttrs" in result.stdout
        assert "test_attr" in result.stdout
        assert "count" in result.stdout
    finally:
        # Clean up
        registry._nodes.pop("TestNodeWithAttrs", None)
        registry._metadata.pop("TestNodeWithAttrs", None)


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
        settings = resolve_settings(
            profile=None,
            api_url=None,
            service_token=None,
            offline=False,
        )
        # Should use default localhost:8000
        assert settings.api_url == "http://localhost:8000"
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


def test_code_template_creates_workflow_file(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test that code template command creates a workflow file."""
    output_file = tmp_path / "test_workflow.py"
    result = runner.invoke(
        app,
        ["code", "template", "--output", str(output_file)],
        env=env,
    )
    assert result.exit_code == 0
    assert output_file.exists()
    content = output_file.read_text()
    assert "from langgraph.graph import END, START, StateGraph" in content
    assert "def build_graph():" in content
    assert "Created workflow template" in result.stdout


def test_code_template_uses_default_filename(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test that code template uses default workflow.py filename."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(app, ["code", "template"], env=env)
        assert result.exit_code == 0
        assert Path("workflow.py").exists()
        assert "Created workflow template: workflow.py" in result.stdout


def test_code_template_prevents_overwrite_without_force(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test template prevents overwriting existing files without --force."""
    output_file = tmp_path / "existing.py"
    output_file.write_text("# existing content")

    result = runner.invoke(
        app,
        ["code", "template", "--output", str(output_file)],
        env=env,
    )
    assert result.exit_code == 1
    assert "already exists" in result.stdout
    assert "--force" in result.stdout
    # Original content should be preserved
    assert output_file.read_text() == "# existing content"


def test_code_template_overwrites_with_force(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test that template command overwrites with --force flag."""
    output_file = tmp_path / "existing.py"
    output_file.write_text("# existing content")

    result = runner.invoke(
        app,
        ["code", "template", "--output", str(output_file), "--force"],
        env=env,
    )
    assert result.exit_code == 0
    content = output_file.read_text()
    assert "# existing content" not in content
    assert "from langgraph.graph import END, START, StateGraph" in content


def test_code_template_includes_next_steps(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test that template command shows next steps to user."""
    output_file = tmp_path / "workflow.py"
    result = runner.invoke(
        app,
        ["code", "template", "--output", str(output_file)],
        env=env,
    )
    assert result.exit_code == 0
    assert "Next steps:" in result.stdout
    assert "Edit" in result.stdout
    assert "Test locally" in result.stdout
    assert "Upload to Orcheo" in result.stdout


def test_code_template_fails_when_output_is_directory(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test that template command fails when output path is a directory."""
    output_dir = tmp_path / "my_dir"
    output_dir.mkdir()

    result = runner.invoke(
        app,
        ["code", "template", "--output", str(output_dir)],
        env=env,
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "is a directory" in str(result.exception)
    assert "provide a file path" in str(result.exception)


def test_code_template_fails_when_parent_is_file(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test that template command fails when parent path is a file."""
    parent_file = tmp_path / "parent.txt"
    parent_file.write_text("I am a file")
    output_path = parent_file / "workflow.py"

    result = runner.invoke(
        app,
        ["code", "template", "--output", str(output_path)],
        env=env,
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "is not a directory" in str(result.exception)


def test_code_template_creates_parent_directories(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test that template command creates parent directories if they don't exist."""
    output_file = tmp_path / "nested" / "dirs" / "workflow.py"

    result = runner.invoke(
        app,
        ["code", "template", "--output", str(output_file)],
        env=env,
    )
    assert result.exit_code == 0
    assert output_file.exists()
    assert output_file.parent.is_dir()
    content = output_file.read_text()
    assert "from langgraph.graph import END, START, StateGraph" in content


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


def test_workflow_mermaid_with_langgraph_summary() -> None:
    """Test mermaid generation when graph contains a LangGraph summary payload."""
    from orcheo_sdk.cli.workflow import _mermaid_from_graph

    graph = {
        "format": "langgraph-script",
        "source": "def build(): ...",
        "summary": {
            "nodes": [{"name": "store_secret", "type": "SetVariableNode"}],
            "edges": [["START", "store_secret"], ["store_secret", "END"]],
            "conditional_edges": [],
        },
    }

    mermaid = _mermaid_from_graph(graph)
    assert "store_secret" in mermaid
    assert "__start__ --> store_secret" in mermaid
    assert "store_secret --> __end__" in mermaid


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


# Workflow mermaid generation tests for edge cases
def test_workflow_mermaid_node_identifier_none() -> None:
    """Test node identifier returns None for nodes without id/name/label/type."""
    from orcheo_sdk.cli.workflow import _node_identifier

    # Test with mapping with None value
    result = _node_identifier({"other_field": "value"})
    assert result is None

    # Test with None node
    result = _node_identifier(None)
    assert result is None


def test_workflow_mermaid_identity_state() -> None:
    """Test _identity_state function returns state unchanged."""
    from orcheo_sdk.cli.workflow import _identity_state

    state = {"key": "value", "nested": {"data": 123}}
    result = _identity_state(state, "arg1", "arg2", kwarg="test")
    assert result == state
    assert result is state


def test_workflow_mermaid_collect_node_names_with_none_identifier() -> None:
    """Test _collect_node_names skips nodes with None identifier."""
    from orcheo_sdk.cli.workflow import _collect_node_names

    nodes = [
        {"id": "node1"},
        {"other": "field"},  # No id/name/label/type
        None,  # None node
        {"id": "node2"},
    ]
    names = _collect_node_names(nodes)
    assert names == {"node1", "node2"}


def test_workflow_mermaid_resolve_edge_with_wrong_length_list() -> None:
    """Test _resolve_edge returns None for list with wrong length."""
    from orcheo_sdk.cli.workflow import _resolve_edge

    # List with 1 element
    result = _resolve_edge(["single"])
    assert result is None

    # List with 3 elements
    result = _resolve_edge(["a", "b", "c"])
    assert result is None

    # Empty list
    result = _resolve_edge([])
    assert result is None


def test_workflow_mermaid_resolve_edge_with_non_sequence_non_mapping() -> None:
    """Test _resolve_edge returns None for non-sequence non-mapping input."""
    from orcheo_sdk.cli.workflow import _resolve_edge

    # Integer
    result = _resolve_edge(123)
    assert result is None

    # Float
    result = _resolve_edge(45.6)
    assert result is None

    # Boolean
    result = _resolve_edge(True)
    assert result is None


def test_workflow_mermaid_resolve_edge_with_missing_source_or_target() -> None:
    """Test _resolve_edge returns None when source or target is missing."""
    from orcheo_sdk.cli.workflow import _resolve_edge

    # Mapping with empty source
    result = _resolve_edge({"from": "", "to": "target"})
    assert result is None

    # Mapping with empty target
    result = _resolve_edge({"from": "source", "to": ""})
    assert result is None

    # Mapping with None source
    result = _resolve_edge({"from": None, "to": "target"})
    assert result is None


def test_workflow_mermaid_register_endpoint_with_start_and_end() -> None:
    """Test _register_endpoint does not add START or END to node_names."""
    from orcheo_sdk.cli.workflow import _register_endpoint

    node_names: set[str] = set()

    _register_endpoint(node_names, "START")
    assert "START" not in node_names

    _register_endpoint(node_names, "start")
    assert "start" not in node_names

    _register_endpoint(node_names, "END")
    assert "END" not in node_names

    _register_endpoint(node_names, "end")
    assert "end" not in node_names

    _register_endpoint(node_names, "regular_node")
    assert "regular_node" in node_names


def test_workflow_mermaid_normalise_vertex_with_start() -> None:
    """Test _normalise_vertex converts 'START' to start sentinel."""
    from langgraph.graph import END, START
    from orcheo_sdk.cli.workflow import _normalise_vertex

    result = _normalise_vertex("START", START, END)
    assert result is START

    result = _normalise_vertex("start", START, END)
    assert result is START


def test_workflow_mermaid_normalise_vertex_with_end() -> None:
    """Test _normalise_vertex converts 'END' to end sentinel."""
    from langgraph.graph import END, START
    from orcheo_sdk.cli.workflow import _normalise_vertex

    result = _normalise_vertex("END", START, END)
    assert result is END

    result = _normalise_vertex("end", START, END)
    assert result is END


def test_workflow_mermaid_no_edges_with_nodes() -> None:
    """Test mermaid generation when there are nodes but no edges."""
    from orcheo_sdk.cli.workflow import _compiled_mermaid

    graph = {"nodes": [{"id": "node1"}, {"id": "node2"}], "edges": []}
    mermaid = _compiled_mermaid(graph)
    # Should add START -> first node edge automatically
    assert "node1" in mermaid


def test_workflow_mermaid_no_edges_no_nodes() -> None:
    """Test mermaid generation when there are no nodes and no edges."""
    from orcheo_sdk.cli.workflow import _compiled_mermaid

    graph = {"nodes": [], "edges": []}
    mermaid = _compiled_mermaid(graph)
    # Should add START -> END edge
    assert mermaid is not None


def test_workflow_mermaid_edges_without_start() -> None:
    """Test mermaid generation when edges exist but none start from START."""
    from orcheo_sdk.cli.workflow import _compiled_mermaid

    graph = {
        "nodes": [{"id": "node1"}, {"id": "node2"}, {"id": "node3"}],
        "edges": [{"from": "node1", "to": "node2"}, {"from": "node2", "to": "node3"}],
    }
    mermaid = _compiled_mermaid(graph)
    # Should add START -> node1 edge (first node not in targets)
    assert mermaid is not None


def test_workflow_mermaid_edges_without_start_all_nodes_are_targets() -> None:
    """Test mermaid fallback when all nodes are targets (circular or no entry)."""
    from orcheo_sdk.cli.workflow import _compiled_mermaid

    graph = {
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}],  # Circular
    }
    mermaid = _compiled_mermaid(graph)
    # Should add START -> first edge source as fallback
    assert mermaid is not None


def test_workflow_mermaid_with_complex_edge_scenarios() -> None:
    """Test mermaid generation with various complex edge scenarios."""
    from orcheo_sdk.cli.workflow import _compiled_mermaid

    # Test with multiple nodes and complex routing
    graph = {
        "nodes": [
            {"id": "start_node"},
            {"id": "middle_node"},
            {"id": "end_node"},
        ],
        "edges": [
            {"from": "START", "to": "start_node"},
            {"from": "start_node", "to": "middle_node"},
            {"from": "middle_node", "to": "end_node"},
            {"from": "end_node", "to": "END"},
        ],
    }
    mermaid = _compiled_mermaid(graph)
    assert mermaid is not None
    assert "start_node" in mermaid
    assert "middle_node" in mermaid
    assert "end_node" in mermaid


def test_workflow_show_with_mermaid_generation(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow show generates mermaid diagram with various edge cases."""
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {
                "nodes": [{"id": "start_node"}, {"id": "end_node"}],
                "edges": [
                    {"from": "START", "to": "start_node"},
                    {"from": "start_node", "to": "end_node"},
                    {"from": "end_node", "to": "END"},
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
    assert "start_node" in result.stdout
    assert "end_node" in result.stdout


# Workflow upload tests
def test_workflow_upload_python_file_offline_error(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload fails in offline mode."""
    py_file = tmp_path / "workflow.py"
    py_file.write_text("workflow = None", encoding="utf-8")
    result = runner.invoke(
        app,
        ["--offline", "workflow", "upload", str(py_file)],
        env=env,
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "network connectivity" in str(result.exception)


def test_workflow_upload_file_not_exists(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow upload fails when file does not exist."""
    result = runner.invoke(
        app,
        ["workflow", "upload", "/nonexistent/file.py"],
        env=env,
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "does not exist" in str(result.exception)


def test_workflow_upload_path_is_not_file(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload fails when path is not a file."""
    result = runner.invoke(
        app,
        ["workflow", "upload", str(tmp_path)],
        env=env,
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "is not a file" in str(result.exception)


def test_workflow_upload_unsupported_file_type(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload fails with unsupported file extension."""
    txt_file = tmp_path / "workflow.txt"
    txt_file.write_text("some content", encoding="utf-8")
    result = runner.invoke(
        app,
        ["workflow", "upload", str(txt_file)],
        env=env,
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "Unsupported file type" in str(result.exception)


def test_workflow_upload_python_file_create_new(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload creates new workflow from Python file."""
    py_file = tmp_path / "workflow.py"
    py_file.write_text(
        """
from orcheo_sdk import Workflow

workflow = Workflow(name="TestWorkflow")
""",
        encoding="utf-8",
    )

    created = {"id": "wf-new", "name": "TestWorkflow"}
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows").mock(
            return_value=httpx.Response(201, json=created)
        )
        result = runner.invoke(
            app,
            ["workflow", "upload", str(py_file)],
            env=env,
        )
    assert result.exit_code == 0
    assert "uploaded successfully" in result.stdout


def test_workflow_upload_python_file_update_existing(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload updates existing workflow from Python file."""
    py_file = tmp_path / "workflow.py"
    py_file.write_text(
        """
from orcheo_sdk import Workflow

workflow = Workflow(name="TestWorkflow")
""",
        encoding="utf-8",
    )

    updated = {"id": "wf-1", "name": "TestWorkflow"}
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=updated)
        )
        result = runner.invoke(
            app,
            ["workflow", "upload", str(py_file), "--id", "wf-1"],
            env=env,
        )
    assert result.exit_code == 0
    assert "updated successfully" in result.stdout


def test_workflow_upload_python_file_create_new_with_name_override(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload allows renaming when creating from Python file."""
    py_file = tmp_path / "workflow.py"
    py_file.write_text(
        """
from orcheo_sdk import Workflow

workflow = Workflow(name="TestWorkflow")
""",
        encoding="utf-8",
    )

    created = {"id": "wf-new", "name": "Renamed Workflow"}
    with respx.mock(assert_all_called=True) as router:
        create_route = router.post("http://api.test/api/workflows").mock(
            return_value=httpx.Response(201, json=created)
        )
        result = runner.invoke(
            app,
            ["workflow", "upload", str(py_file), "--name", "Renamed Workflow"],
            env=env,
        )
    assert result.exit_code == 0
    body = json.loads(create_route.calls[0].request.content)
    assert body["name"] == "Renamed Workflow"


def test_workflow_upload_python_file_update_existing_with_name_override(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload allows renaming when updating from Python file."""
    py_file = tmp_path / "workflow.py"
    py_file.write_text(
        """
from orcheo_sdk import Workflow

workflow = Workflow(name="OldName")
""",
        encoding="utf-8",
    )

    updated = {"id": "wf-1", "name": "Renamed Workflow"}
    with respx.mock(assert_all_called=True) as router:
        update_route = router.post("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=updated)
        )
        result = runner.invoke(
            app,
            [
                "workflow",
                "upload",
                str(py_file),
                "--id",
                "wf-1",
                "--name",
                "Renamed Workflow",
            ],
            env=env,
        )
    assert result.exit_code == 0
    body = json.loads(update_route.calls[0].request.content)
    assert body["name"] == "Renamed Workflow"


def test_workflow_upload_json_file_create_new(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload creates new workflow from JSON file."""
    json_file = tmp_path / "workflow.json"
    json_file.write_text(
        json.dumps({"name": "TestWorkflow", "graph": {"nodes": [], "edges": []}}),
        encoding="utf-8",
    )

    created = {"id": "wf-new", "name": "TestWorkflow"}
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows").mock(
            return_value=httpx.Response(201, json=created)
        )
        result = runner.invoke(
            app,
            ["workflow", "upload", str(json_file)],
            env=env,
        )
    assert result.exit_code == 0
    assert "uploaded successfully" in result.stdout


def test_workflow_upload_json_file_update_existing(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload updates existing workflow from JSON file."""
    json_file = tmp_path / "workflow.json"
    json_file.write_text(
        json.dumps({"name": "TestWorkflow", "graph": {"nodes": [], "edges": []}}),
        encoding="utf-8",
    )

    updated = {"id": "wf-1", "name": "TestWorkflow"}
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=updated)
        )
        result = runner.invoke(
            app,
            ["workflow", "upload", str(json_file), "--id", "wf-1"],
            env=env,
        )
    assert result.exit_code == 0
    assert "updated successfully" in result.stdout


# Workflow download tests
def test_workflow_download_json_to_stdout(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow download outputs JSON to stdout."""
    workflow = {"id": "wf-1", "name": "Test", "metadata": {"key": "value"}}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {"nodes": [{"id": "a"}], "edges": []},
        }
    ]

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1"],
            env=env,
        )
    assert result.exit_code == 0
    assert '"name": "Test"' in result.stdout
    assert '"metadata"' in result.stdout


def test_workflow_download_json_to_file(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow download saves JSON to file."""
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {"nodes": [{"id": "a"}], "edges": []},
        }
    ]
    output_file = tmp_path / "output.json"

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1", "--output", str(output_file)],
            env=env,
        )
    assert result.exit_code == 0
    assert "downloaded to" in result.stdout
    assert output_file.exists()
    content = json.loads(output_file.read_text(encoding="utf-8"))
    assert content["name"] == "Test"


def test_workflow_download_python_to_stdout(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow download outputs Python code to stdout."""
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {
                "nodes": [
                    {"name": "node1", "type": "Agent"},
                    {"name": "node2", "type": "Agent"},
                ],
                "edges": [],
            },
        }
    ]

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1", "--format", "python"],
            env=env,
        )
    assert result.exit_code == 0
    assert "from orcheo_sdk import Workflow" in result.stdout
    assert "class AgentConfig" in result.stdout
    assert "class AgentNode" in result.stdout


def test_workflow_download_python_to_file(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow download saves Python code to file."""
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {
                "nodes": [{"name": "node1", "type": "Code"}],
                "edges": [],
            },
        }
    ]
    output_file = tmp_path / "output.py"

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            [
                "workflow",
                "download",
                "wf-1",
                "--format",
                "python",
                "-o",
                str(output_file),
            ],
            env=env,
        )
    assert result.exit_code == 0
    assert "downloaded to" in result.stdout
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "from orcheo_sdk import Workflow" in content


def test_workflow_download_no_versions_error(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow download fails when workflow has no versions."""
    workflow = {"id": "wf-1", "name": "Test"}
    versions: list[dict] = []

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1"],
            env=env,
        )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "has no versions" in str(result.exception)


def test_workflow_download_unsupported_format_error(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow download fails with unsupported format."""
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {"nodes": [], "edges": []},
        }
    ]

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1", "--format", "yaml"],
            env=env,
        )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "Unsupported format" in str(result.exception)


def test_workflow_download_langgraph_script_returns_original_source(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow download returns original LangGraph script source."""
    original_source = """from langgraph.graph import StateGraph
from typing import TypedDict

class State(TypedDict):
    messages: list[str]

def my_node(state: State) -> State:
    return {"messages": state["messages"] + ["processed"]}

graph = StateGraph(State)
graph.add_node("my_node", my_node)
graph.set_entry_point("my_node")
graph.set_finish_point("my_node")
"""
    workflow = {"id": "wf-1", "name": "LangGraphWorkflow"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {
                "format": "langgraph-script",
                "source": original_source,
                "entrypoint": None,
                "summary": {
                    "nodes": [{"name": "my_node", "type": "function"}],
                    "edges": [],
                },
            },
        }
    ]

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1", "--format", "python"],
            env=env,
        )
    assert result.exit_code == 0
    assert "from langgraph.graph import StateGraph" in result.stdout
    assert "def my_node(state: State)" in result.stdout
    # Should NOT contain SDK template code
    assert "from orcheo_sdk import Workflow" not in result.stdout


def test_workflow_download_langgraph_script_json_includes_source(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow download as JSON includes original LangGraph source."""
    original_source = "from langgraph.graph import StateGraph\n"
    workflow = {"id": "wf-1", "name": "LangGraphWorkflow"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {
                "format": "langgraph-script",
                "source": original_source,
                "entrypoint": None,
                "summary": {"nodes": [], "edges": []},
            },
        }
    ]

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1", "--format", "json"],
            env=env,
        )
    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert output["graph"]["format"] == "langgraph-script"
    assert output["graph"]["source"] == original_source


def test_workflow_download_auto_format_langgraph_script(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test download with auto format: LangGraph script downloads as Python."""
    original_source = """from langgraph.graph import StateGraph

def my_node(state):
    return state

graph = StateGraph(dict)
graph.add_node("my_node", my_node)
"""
    workflow = {"id": "wf-1", "name": "LangGraphWorkflow"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {
                "format": "langgraph-script",
                "source": original_source,
                "entrypoint": None,
                "summary": {"nodes": [{"name": "my_node"}], "edges": []},
            },
        }
    ]

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1"],  # No --format, should default to auto
            env=env,
        )
    assert result.exit_code == 0
    # Should output Python code (not JSON)
    assert "from langgraph.graph import StateGraph" in result.stdout
    assert "def my_node(state)" in result.stdout
    # Should NOT contain JSON structure
    assert '"name"' not in result.stdout


def test_workflow_download_auto_format_sdk_workflow(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow download with auto format for SDK workflow downloads as JSON."""
    workflow = {"id": "wf-1", "name": "SDKWorkflow"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {
                # No "format" field or format is not "langgraph-script"
                "nodes": [{"name": "node1", "type": "Agent"}],
                "edges": [],
            },
        }
    ]

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1"],  # No --format, should default to auto
            env=env,
        )
    assert result.exit_code == 0
    # Should output JSON (not Python code)
    output = json.loads(result.stdout)
    assert output["name"] == "SDKWorkflow"
    assert "graph" in output


def test_workflow_download_auto_format_missing_graph(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Gracefully handle workflows whose versions lack a graph payload."""
    workflow = {"id": "wf-1", "name": "SDKWorkflow"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            # Older versions may omit the "graph" field altogether.
            # The CLI should fall back to JSON output without crashing.
        }
    ]

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1"],  # No --format, should default to auto
            env=env,
        )
    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert output["name"] == "SDKWorkflow"
    assert output["graph"] == {}


def test_workflow_download_auto_format_explicit(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow download with explicit --format auto for LangGraph script."""
    original_source = "from langgraph.graph import StateGraph\n"
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {
                "format": "langgraph-script",
                "source": original_source,
                "entrypoint": None,
                "summary": {"nodes": [], "edges": []},
            },
        }
    ]

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1", "--format", "auto"],
            env=env,
        )
    assert result.exit_code == 0
    # Should output Python code
    assert original_source in result.stdout


# Python workflow loading tests
def test_load_workflow_from_python_missing_workflow_variable(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test loading Python file without 'workflow' treats it as LangGraph script."""
    py_file = tmp_path / "no_workflow.py"
    py_file.write_text("some_other_var = 123", encoding="utf-8")

    # Now it treats files without 'workflow' as LangGraph scripts
    # and tries to create a workflow and ingest them
    created_workflow = {"id": "wf-new", "name": "no-workflow"}
    # The ingestion will fail because it's not valid LangGraph code
    with respx.mock() as router:
        router.post("http://api.test/api/workflows").mock(
            return_value=httpx.Response(201, json=created_workflow)
        )
        router.post("http://api.test/api/workflows/wf-new/versions/ingest").mock(
            return_value=httpx.Response(
                400, json={"detail": "Script did not produce a LangGraph StateGraph"}
            )
        )
        result = runner.invoke(
            app,
            ["workflow", "upload", str(py_file)],
            env=env,
        )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "Failed to ingest LangGraph script" in str(result.exception)


def test_load_workflow_from_python_wrong_type(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test loading Python file with wrong workflow type fails."""
    py_file = tmp_path / "wrong_type.py"
    py_file.write_text("workflow = 'not a Workflow instance'", encoding="utf-8")

    result = runner.invoke(
        app,
        ["workflow", "upload", str(py_file)],
        env=env,
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "must be an orcheo_sdk.Workflow instance" in str(result.exception)


# JSON workflow loading tests
def test_load_workflow_from_json_not_object(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test loading JSON file that is not an object fails."""
    json_file = tmp_path / "array.json"
    json_file.write_text('["not", "an", "object"]', encoding="utf-8")

    result = runner.invoke(
        app,
        ["workflow", "upload", str(json_file)],
        env=env,
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "must contain a JSON object" in str(result.exception)


def test_load_workflow_from_json_missing_name(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test loading JSON file without 'name' field fails."""
    json_file = tmp_path / "no_name.json"
    json_file.write_text('{"graph": {}}', encoding="utf-8")

    result = runner.invoke(
        app,
        ["workflow", "upload", str(json_file)],
        env=env,
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "must include a 'name' field" in str(result.exception)


def test_load_workflow_from_json_missing_graph(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test loading JSON file without 'graph' field fails."""
    json_file = tmp_path / "no_graph.json"
    json_file.write_text('{"name": "Test"}', encoding="utf-8")

    result = runner.invoke(
        app,
        ["workflow", "upload", str(json_file)],
        env=env,
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "must include a 'graph' field" in str(result.exception)


# Format workflow tests
def test_format_workflow_as_json_without_metadata(tmp_path: Path) -> None:
    """Test formatting workflow as JSON without metadata."""
    from orcheo_sdk.cli.workflow import _format_workflow_as_json

    workflow = {"id": "wf-1", "name": "Test"}
    graph = {"nodes": [{"id": "a"}], "edges": []}

    result = _format_workflow_as_json(workflow, graph)
    data = json.loads(result)

    assert data["name"] == "Test"
    assert data["graph"] == graph
    assert "metadata" not in data


def test_format_workflow_as_json_with_metadata(tmp_path: Path) -> None:
    """Test formatting workflow as JSON with metadata."""
    from orcheo_sdk.cli.workflow import _format_workflow_as_json

    workflow = {"id": "wf-1", "name": "Test", "metadata": {"key": "value"}}
    graph = {"nodes": [{"id": "a"}], "edges": []}

    result = _format_workflow_as_json(workflow, graph)
    data = json.loads(result)

    assert data["name"] == "Test"
    assert data["graph"] == graph
    assert data["metadata"] == {"key": "value"}


def test_format_workflow_as_python_multiple_node_types(tmp_path: Path) -> None:
    """Test formatting workflow as Python with multiple node types."""
    from orcheo_sdk.cli.workflow import _format_workflow_as_python

    workflow = {"name": "TestWorkflow"}
    graph = {
        "nodes": [
            {"name": "agent1", "type": "Agent"},
            {"name": "agent2", "type": "Agent"},
            {"name": "code1", "type": "Code"},
        ],
        "edges": [],
    }

    result = _format_workflow_as_python(workflow, graph)

    assert 'workflow = Workflow(name="TestWorkflow")' in result
    assert "class AgentConfig(BaseModel):" in result
    assert "class AgentNode(WorkflowNode[AgentConfig]):" in result
    assert "class CodeConfig(BaseModel):" in result
    assert "class CodeNode(WorkflowNode[CodeConfig]):" in result
    # Should not duplicate Agent classes
    assert result.count("class AgentConfig") == 1
    assert "# TODO: Configure node dependencies" in result


def test_format_workflow_as_python_empty_nodes(tmp_path: Path) -> None:
    """Test formatting workflow as Python with no nodes."""
    from orcheo_sdk.cli.workflow import _format_workflow_as_python

    workflow = {"name": "EmptyWorkflow"}
    graph = {"nodes": [], "edges": []}

    result = _format_workflow_as_python(workflow, graph)

    assert 'workflow = Workflow(name="EmptyWorkflow")' in result
    assert "from orcheo_sdk import Workflow" in result


def test_workflow_download_with_cache_notice(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow download shows cache notice when using cached data."""
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {"nodes": [{"id": "a"}], "edges": []},
        }
    ]

    # First call to populate cache
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        first = runner.invoke(
            app,
            ["workflow", "download", "wf-1"],
            env=env,
        )
        assert first.exit_code == 0

    # Second call in offline mode should use cache and show notice
    result = runner.invoke(
        app,
        ["--offline", "workflow", "download", "wf-1"],
        env=env,
    )
    assert result.exit_code == 0
    assert "Using cached data" in result.stdout


def test_workflow_upload_python_spec_loading_failure(
    runner: CliRunner,
    env: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test workflow upload handles spec_from_file_location failure."""
    import importlib.util

    py_file = tmp_path / "workflow.py"
    py_file.write_text("workflow = None", encoding="utf-8")

    # Mock spec_from_file_location to return None
    def mock_spec_from_file_location(name: str, location: object) -> None:
        return None

    monkeypatch.setattr(
        importlib.util, "spec_from_file_location", mock_spec_from_file_location
    )

    result = runner.invoke(
        app,
        ["workflow", "upload", str(py_file)],
        env=env,
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "Failed to load Python module" in str(result.exception)


def test_workflow_upload_langgraph_script_create_new(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload creates new workflow from LangGraph script."""
    py_file = tmp_path / "langgraph_workflow.py"
    py_file.write_text(
        """
from langgraph.graph import StateGraph

def greet(state):
    return {"message": "Hello"}

def build_graph():
    graph = StateGraph(dict)
    graph.add_node("greet", greet)
    graph.set_entry_point("greet")
    graph.set_finish_point("greet")
    return graph
""",
        encoding="utf-8",
    )

    created_workflow = {"id": "wf-new", "name": "langgraph-workflow"}
    created_version = {"id": "v-1", "version": 1, "workflow_id": "wf-new"}
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows").mock(
            return_value=httpx.Response(201, json=created_workflow)
        )
        router.post("http://api.test/api/workflows/wf-new/versions/ingest").mock(
            return_value=httpx.Response(201, json=created_version)
        )
        result = runner.invoke(
            app,
            ["workflow", "upload", str(py_file)],
            env=env,
        )
    assert result.exit_code == 0
    assert "Created workflow" in result.stdout
    assert "Ingested LangGraph script as version 1" in result.stdout


def test_workflow_upload_langgraph_script_update_existing(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload adds version to existing workflow from LangGraph."""
    py_file = tmp_path / "langgraph_workflow.py"
    py_file.write_text(
        """
from langgraph.graph import StateGraph

def greet(state):
    return {"message": "Hello Updated"}

def build_graph():
    graph = StateGraph(dict)
    graph.add_node("greet", greet)
    graph.set_entry_point("greet")
    graph.set_finish_point("greet")
    return graph
""",
        encoding="utf-8",
    )

    existing_workflow = {"id": "wf-1", "name": "existing"}
    created_version = {"id": "v-2", "version": 2, "workflow_id": "wf-1"}
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=existing_workflow)
        )
        router.post("http://api.test/api/workflows/wf-1/versions/ingest").mock(
            return_value=httpx.Response(201, json=created_version)
        )
        result = runner.invoke(
            app,
            ["workflow", "upload", str(py_file), "--id", "wf-1"],
            env=env,
        )
    assert result.exit_code == 0
    assert "Ingested LangGraph script as version 2" in result.stdout


def test_workflow_upload_langgraph_script_fetch_existing_error(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload fails when fetching existing workflow fails."""
    py_file = tmp_path / "langgraph_workflow.py"
    py_file.write_text(
        """
from langgraph.graph import StateGraph

def greet(state):
    return {"message": "Hello"}
""",
        encoding="utf-8",
    )

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(404, json={"error": "Not found"})
        )
        result = runner.invoke(
            app,
            ["workflow", "upload", str(py_file), "--id", "wf-1"],
            env=env,
        )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "Failed to fetch workflow" in str(result.exception)


def test_workflow_upload_langgraph_script_create_workflow_error(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload fails when creating new workflow fails."""
    py_file = tmp_path / "langgraph_workflow.py"
    py_file.write_text(
        """
from langgraph.graph import StateGraph

def greet(state):
    return {"message": "Hello"}
""",
        encoding="utf-8",
    )

    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows").mock(
            return_value=httpx.Response(500, json={"error": "Internal error"})
        )
        result = runner.invoke(
            app,
            ["workflow", "upload", str(py_file)],
            env=env,
        )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "Failed to create workflow" in str(result.exception)


def test_workflow_upload_langgraph_script_with_entrypoint(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload with custom entrypoint."""
    py_file = tmp_path / "langgraph_workflow.py"
    py_file.write_text(
        """
from langgraph.graph import StateGraph

def my_custom_graph():
    graph = StateGraph(dict)
    return graph
""",
        encoding="utf-8",
    )

    created_workflow = {"id": "wf-new", "name": "langgraph-workflow"}
    created_version = {"id": "v-1", "version": 1, "workflow_id": "wf-new"}
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows").mock(
            return_value=httpx.Response(201, json=created_workflow)
        )
        ingest_route = router.post(
            "http://api.test/api/workflows/wf-new/versions/ingest"
        ).mock(return_value=httpx.Response(201, json=created_version))
        result = runner.invoke(
            app,
            ["workflow", "upload", str(py_file), "--entrypoint", "my_custom_graph"],
            env=env,
        )
    assert result.exit_code == 0
    # Verify the entrypoint was passed in the request
    request_body = json.loads(ingest_route.calls[0].request.content)
    assert request_body["entrypoint"] == "my_custom_graph"


def test_workflow_upload_langgraph_script_create_new_with_name_override(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test LangGraph upload allows renaming during creation."""
    py_file = tmp_path / "langgraph_workflow.py"
    py_file.write_text(
        """
from langgraph.graph import StateGraph

def build_graph():
    graph = StateGraph(dict)
    return graph
""",
        encoding="utf-8",
    )

    created_workflow = {"id": "wf-new", "name": "custom-workflow"}
    created_version = {"id": "v-1", "version": 1, "workflow_id": "wf-new"}
    with respx.mock(assert_all_called=True) as router:
        create_route = router.post("http://api.test/api/workflows").mock(
            return_value=httpx.Response(201, json=created_workflow)
        )
        router.post("http://api.test/api/workflows/wf-new/versions/ingest").mock(
            return_value=httpx.Response(201, json=created_version)
        )
        result = runner.invoke(
            app,
            [
                "workflow",
                "upload",
                str(py_file),
                "--name",
                "Custom Workflow",
            ],
            env=env,
        )
    assert result.exit_code == 0
    body = json.loads(create_route.calls[0].request.content)
    assert body["name"] == "Custom Workflow"
    assert body["slug"] == "custom-workflow"


def test_workflow_upload_langgraph_script_update_existing_with_name_override(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test LangGraph upload renames existing workflow before ingest."""
    py_file = tmp_path / "langgraph_workflow.py"
    py_file.write_text(
        """
from langgraph.graph import StateGraph

def build_graph():
    graph = StateGraph(dict)
    return graph
""",
        encoding="utf-8",
    )

    existing_workflow = {"id": "wf-1", "name": "Old"}
    created_version = {"id": "v-2", "version": 2, "workflow_id": "wf-1"}
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=existing_workflow)
        )
        rename_route = router.post("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(
                200, json={"id": "wf-1", "name": "Renamed Workflow"}
            )
        )
        ingest_route = router.post(
            "http://api.test/api/workflows/wf-1/versions/ingest"
        ).mock(return_value=httpx.Response(201, json=created_version))
        result = runner.invoke(
            app,
            [
                "workflow",
                "upload",
                str(py_file),
                "--id",
                "wf-1",
                "--name",
                "Renamed Workflow",
            ],
            env=env,
        )
    assert result.exit_code == 0
    rename_body = json.loads(rename_route.calls[0].request.content)
    assert rename_body["name"] == "Renamed Workflow"
    # Ensure ingest still occurs
    assert ingest_route.calls


def test_workflow_upload_with_blank_name_error(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload rejects empty rename values."""
    json_file = tmp_path / "workflow.json"
    json_file.write_text(
        json.dumps({"name": "Original", "graph": {"nodes": [], "edges": []}}),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["workflow", "upload", str(json_file), "--name", "   "],
        env=env,
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "cannot be empty" in str(result.exception)


def test_strip_main_block_single_quotes(tmp_path: Path) -> None:
    """Test _strip_main_block removes if __name__ with single quotes."""
    from orcheo_sdk.cli.workflow import _strip_main_block

    script = """
def hello():
    return "world"

if __name__ == '__main__':
    hello()
"""
    result = _strip_main_block(script)
    assert "if __name__" not in result
    assert "    hello()" not in result
    assert "def hello():" in result


def test_strip_main_block_double_quotes(tmp_path: Path) -> None:
    """Test _strip_main_block removes if __name__ with double quotes."""
    from orcheo_sdk.cli.workflow import _strip_main_block

    script = """
def hello():
    return "world"

if __name__ == "__main__":
    hello()
"""
    result = _strip_main_block(script)
    assert "if __name__" not in result
    assert "    hello()" not in result
    assert "def hello():" in result


def test_handle_status_update_error() -> None:
    """Test _handle_status_update with error status."""
    import io
    from orcheo_sdk.cli.workflow import _handle_status_update
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"status": "error", "error": "Something went wrong"}
    result = _handle_status_update(state, update)
    assert result == "error"
    assert "Something went wrong" in output.getvalue()


def test_handle_status_update_error_no_detail() -> None:
    """Test _handle_status_update with error status but no error detail."""
    import io
    from orcheo_sdk.cli.workflow import _handle_status_update
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"status": "error"}
    result = _handle_status_update(state, update)
    assert result == "error"
    assert "Unknown error" in output.getvalue()


def test_handle_status_update_cancelled() -> None:
    """Test _handle_status_update with cancelled status."""
    import io
    from orcheo_sdk.cli.workflow import _handle_status_update
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"status": "cancelled", "reason": "User stopped it"}
    result = _handle_status_update(state, update)
    assert result == "cancelled"
    assert "User stopped it" in output.getvalue()


def test_handle_status_update_cancelled_no_reason() -> None:
    """Test _handle_status_update with cancelled status but no reason."""
    import io
    from orcheo_sdk.cli.workflow import _handle_status_update
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"status": "cancelled"}
    result = _handle_status_update(state, update)
    assert result == "cancelled"
    assert "No reason provided" in output.getvalue()


def test_handle_status_update_completed() -> None:
    """Test _handle_status_update with completed status."""
    import io
    from orcheo_sdk.cli.workflow import _handle_status_update
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"status": "completed"}
    result = _handle_status_update(state, update)
    assert result == "completed"
    assert "completed successfully" in output.getvalue()


def test_handle_status_update_other_status() -> None:
    """Test _handle_status_update with other status."""
    import io
    from orcheo_sdk.cli.workflow import _handle_status_update
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"status": "running"}
    result = _handle_status_update(state, update)
    assert result is None
    assert "running" in output.getvalue()


def test_handle_node_event_on_chain_start() -> None:
    """Test _handle_node_event with on_chain_start event."""
    import io
    from orcheo_sdk.cli.workflow import _handle_node_event
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"node": "test_node", "event": "on_chain_start"}
    _handle_node_event(state, update)
    assert "test_node" in output.getvalue()
    assert "starting" in output.getvalue()


def test_handle_node_event_on_chain_end() -> None:
    """Test _handle_node_event with on_chain_end event."""
    import io
    from orcheo_sdk.cli.workflow import _handle_node_event
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {
        "node": "test_node",
        "event": "on_chain_end",
        "payload": {"result": "success"},
    }
    _handle_node_event(state, update)
    assert "test_node" in output.getvalue()


def test_handle_node_event_on_chain_error() -> None:
    """Test _handle_node_event with on_chain_error event."""
    import io
    from orcheo_sdk.cli.workflow import _handle_node_event
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {
        "node": "test_node",
        "event": "on_chain_error",
        "payload": {"error": "Failed to process"},
    }
    _handle_node_event(state, update)
    assert "test_node" in output.getvalue()
    assert "Failed to process" in output.getvalue()


def test_handle_node_event_on_chain_error_no_payload() -> None:
    """Test _handle_node_event with on_chain_error event but no payload."""
    import io
    from orcheo_sdk.cli.workflow import _handle_node_event
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"node": "test_node", "event": "on_chain_error"}
    _handle_node_event(state, update)
    assert "test_node" in output.getvalue()
    assert "Unknown" in output.getvalue()


def test_handle_node_event_other_event() -> None:
    """Test _handle_node_event with other event types."""
    import io
    from orcheo_sdk.cli.workflow import _handle_node_event
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"node": "test_node", "event": "on_chain_stream", "data": "some data"}
    _handle_node_event(state, update)
    assert "test_node" in output.getvalue()
    assert "on_chain_stream" in output.getvalue()


def test_handle_node_event_no_node() -> None:
    """Test _handle_node_event with no node field."""
    import io
    from orcheo_sdk.cli.workflow import _handle_node_event
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"event": "on_chain_start"}
    _handle_node_event(state, update)
    # Should not print anything
    assert output.getvalue() == ""


def test_handle_node_event_no_event() -> None:
    """Test _handle_node_event with no event field."""
    import io
    from orcheo_sdk.cli.workflow import _handle_node_event
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"node": "test_node"}
    _handle_node_event(state, update)
    # Should not print anything
    assert output.getvalue() == ""


def test_render_node_output_small_dict() -> None:
    """Test _render_node_output with small dict."""
    import io
    from orcheo_sdk.cli.workflow import _render_node_output
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    data = {"status": "ok", "count": 42, "flag": True}
    _render_node_output(state, data)
    output_text = output.getvalue()
    assert "status" in output_text
    assert "ok" in output_text


def test_render_node_output_large_dict() -> None:
    """Test _render_node_output with large dict."""
    import io
    from orcheo_sdk.cli.workflow import _render_node_output
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    data = {"a": 1, "b": 2, "c": 3, "d": 4}
    _render_node_output(state, data)
    # Should use JSON rendering for dicts with more than 3 keys
    output_text = output.getvalue()
    assert output_text  # Should have some output


def test_render_node_output_dict_complex_values() -> None:
    """Test _render_node_output with dict containing complex values."""
    import io
    from orcheo_sdk.cli.workflow import _render_node_output
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    data = {"nested": {"value": 1}, "list": [1, 2, 3]}
    _render_node_output(state, data)
    output_text = output.getvalue()
    assert output_text  # Should have some output


def test_render_node_output_short_string() -> None:
    """Test _render_node_output with short string."""
    import io
    from orcheo_sdk.cli.workflow import _render_node_output
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    data = "Hello world"
    _render_node_output(state, data)
    assert "Hello world" in output.getvalue()


def test_render_node_output_long_string() -> None:
    """Test _render_node_output with long string."""
    import io
    from orcheo_sdk.cli.workflow import _render_node_output
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    data = "x" * 150
    _render_node_output(state, data)
    output_text = output.getvalue()
    assert output_text  # Should have some output


def test_render_node_output_other_type() -> None:
    """Test _render_node_output with other data types."""
    import io
    from orcheo_sdk.cli.workflow import _render_node_output
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    data = [1, 2, 3, 4, 5]
    _render_node_output(state, data)
    output_text = output.getvalue()
    assert output_text  # Should have some output


def test_render_node_output_none() -> None:
    """Test _render_node_output with None."""
    import io
    from orcheo_sdk.cli.workflow import _render_node_output
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    _render_node_output(state, None)
    # Should not output anything for None
    assert output.getvalue() == ""


def test_render_node_output_empty_dict() -> None:
    """Test _render_node_output with empty dict."""
    import io
    from orcheo_sdk.cli.workflow import _render_node_output
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    _render_node_output(state, {})
    # Empty dict should not output anything
    assert output.getvalue() == ""


def test_agent_tool_list_shows_all_tools(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test agent-tool list command shows all registered tools."""
    result = runner.invoke(app, ["agent-tool", "list"], env=env)
    assert result.exit_code == 0
    # Should show some tools registered in the registry
    assert "Available Agent Tools" in result.stdout


def test_agent_tool_list_with_category_filter(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test agent-tool list command with category filter."""
    result = runner.invoke(
        app, ["agent-tool", "list", "--category", "general"], env=env
    )
    assert result.exit_code == 0
    assert "Available Agent Tools" in result.stdout


def test_agent_tool_list_with_name_filter(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test agent-tool list command filters by name when category matches."""
    from orcheo.nodes.agent_tools.registry import ToolMetadata, tool_registry

    # Register a test tool
    test_meta = ToolMetadata(
        name="test_search_tool", description="Test search", category="search"
    )

    @tool_registry.register(test_meta)
    def test_tool() -> str:
        return "test"

    result = runner.invoke(app, ["agent-tool", "list", "--category", "search"], env=env)
    assert result.exit_code == 0
    assert "test_search_tool" in result.stdout or "search" in result.stdout.lower()


def test_agent_tool_show_displays_metadata(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test agent-tool show command displays tool metadata."""
    from pydantic import BaseModel, Field
    from orcheo.nodes.agent_tools.registry import ToolMetadata, tool_registry

    class TestSchema(BaseModel):
        query: str = Field(description="The search query")
        limit: int = Field(default=10, description="Result limit")

    # Register a test tool with schema
    test_meta = ToolMetadata(
        name="test_show_tool", description="Test tool for show", category="test"
    )

    @tool_registry.register(test_meta)
    class TestToolWithSchema:
        args_schema = TestSchema

    result = runner.invoke(app, ["agent-tool", "show", "test_show_tool"], env=env)
    assert result.exit_code == 0
    assert "test_show_tool" in result.stdout
    assert "Test tool for show" in result.stdout


def test_agent_tool_show_tool_not_found(runner: CliRunner, env: dict[str, str]) -> None:
    """Test agent-tool show command with non-existent tool."""
    result = runner.invoke(app, ["agent-tool", "show", "nonexistent_tool_xyz"], env=env)
    assert result.exit_code != 0
    assert "not registered" in result.stdout or "not registered" in str(
        result.exception
    )


def test_agent_tool_show_with_pydantic_model(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test agent-tool show with direct Pydantic model."""
    from pydantic import BaseModel, Field
    from orcheo.nodes.agent_tools.registry import ToolMetadata, tool_registry

    class DirectModel(BaseModel):
        """A direct Pydantic model."""

        field: str = Field(default="test", description="A test field")

    test_meta = ToolMetadata(
        name="test_pydantic_model", description="Direct Pydantic", category="test"
    )

    @tool_registry.register(test_meta)
    class ToolWithModel:
        @staticmethod
        def model_json_schema() -> dict:
            return DirectModel.model_json_schema()

    result = runner.invoke(app, ["agent-tool", "show", "test_pydantic_model"], env=env)
    assert result.exit_code == 0
    assert "test_pydantic_model" in result.stdout


def test_agent_tool_show_with_annotations(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test agent-tool show with function annotations."""
    from orcheo.nodes.agent_tools.registry import ToolMetadata, tool_registry

    test_meta = ToolMetadata(
        name="test_annotations_tool",
        description="Function with annotations",
        category="test",
    )

    @tool_registry.register(test_meta)
    def annotated_function(query: str, count: int) -> str:
        """A function with type annotations."""
        return f"{query} {count}"

    result = runner.invoke(
        app, ["agent-tool", "show", "test_annotations_tool"], env=env
    )
    assert result.exit_code == 0
    assert "test_annotations_tool" in result.stdout


def test_agent_tool_show_no_schema(runner: CliRunner, env: dict[str, str]) -> None:
    """Test agent-tool show with tool that has no schema."""
    from orcheo.nodes.agent_tools.registry import ToolMetadata, tool_registry

    test_meta = ToolMetadata(
        name="test_no_schema_tool", description="Tool without schema", category="test"
    )

    @tool_registry.register(test_meta)
    class ToolWithoutSchema:
        pass

    result = runner.invoke(app, ["agent-tool", "show", "test_no_schema_tool"], env=env)
    assert result.exit_code == 0
    assert "test_no_schema_tool" in result.stdout
    assert (
        "No schema information available" in result.stdout
        or "Tool without schema" in result.stdout
    )


def test_agent_tool_show_args_schema_no_model_json_schema(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test agent-tool show with args_schema but no model_json_schema."""
    from orcheo.nodes.agent_tools.registry import ToolMetadata, tool_registry

    test_meta = ToolMetadata(
        name="test_args_no_model",
        description="Tool with args_schema but no model_json_schema",
        category="test",
    )

    class SchemaWithoutMethod:
        pass

    @tool_registry.register(test_meta)
    class ToolWithArgsNoSchema:
        args_schema = SchemaWithoutMethod()

    result = runner.invoke(app, ["agent-tool", "show", "test_args_no_model"], env=env)
    assert result.exit_code == 0
    assert "test_args_no_model" in result.stdout


def test_agent_tool_show_empty_annotations(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test agent-tool show with empty annotations."""
    from orcheo.nodes.agent_tools.registry import ToolMetadata, tool_registry

    test_meta = ToolMetadata(
        name="test_empty_annotations",
        description="Function with empty annotations",
        category="test",
    )

    @tool_registry.register(test_meta)
    def function_no_annotations():
        """Function without annotations."""
        return "test"

    result = runner.invoke(
        app, ["agent-tool", "show", "test_empty_annotations"], env=env
    )
    assert result.exit_code == 0
    assert "test_empty_annotations" in result.stdout
    # Should show "No schema information available" since there are no annotations
    assert "No schema information available" in result.stdout
