from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from rich.console import Console
from typer.testing import CliRunner

import importlib

app_module = importlib.import_module("orcheo_sdk.cli.app")
from orcheo_sdk.cli import app as cli_app
from orcheo_sdk.cli.api import (
    APIClient,
    ApiRequestError,
    FetchResult,
    OfflineCacheMissError,
)
from orcheo_sdk.cli.cache import CacheStore
from orcheo_sdk.cli.code import code_app
from orcheo_sdk.cli.config import (
    CLISettings,
    ProfileNotFoundError,
    load_profiles,
    resolve_settings,
)
from orcheo_sdk.cli.credentials import _find_credential, credential_app
from orcheo_sdk.cli.nodes import _schema_rows, node_app
from orcheo_sdk.cli.render import graph_to_mermaid
from orcheo_sdk.cli.state import CLIContext
from orcheo_sdk.cli.utils import show_cache_notice
from orcheo_sdk.cli.workflows import _format_datetime, workflow_app


def test_api_client_offline_and_http_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = CacheStore(tmp_path)
    cache.ensure()

    class DummyClient:
        def __init__(self, *, base_url: str, timeout: float, headers: dict[str, str]):
            self.base_url = base_url

        def request(self, method: str, path: str, params=None, json=None):  # noqa: ANN001
            request = httpx.Request(method, f"{self.base_url}{path}")
            if path.endswith("/missing"):
                return httpx.Response(404, request=request)
            raise AssertionError("Unexpected path")

        def close(self) -> None:  # pragma: no cover - nothing to clean up
            return None

    monkeypatch.setattr("orcheo_sdk.cli.api.httpx.Client", DummyClient)
    client = APIClient(base_url="https://api.test/api", service_token=None, cache=cache)

    with pytest.raises(OfflineCacheMissError):
        client.get_json("/missing", offline=True, description="demo")

    with pytest.raises(ApiRequestError) as excinfo:
        client.get_json("/missing", description="demo")
    assert "status 404" in str(excinfo.value)


def test_app_callback_configures_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache_dir = tmp_path / "cache"
    responses_dir = cache_dir / "responses"
    settings = CLISettings(
        api_url="https://service.example",
        service_token="token-123",
        profile="dev",
        config_path=tmp_path / "cli.toml",
        cache_dir=cache_dir,
    )

    created_clients: list[DummyClient] = []

    class DummyClient:
        def __init__(
            self,
            *,
            base_url: str,
            service_token: str | None,
            cache: CacheStore,
            timeout: float = 30.0,
        ) -> None:
            self.base_url = base_url
            self.service_token = service_token
            self.cache = cache
            self.timeout = timeout
            self.closed = False
            self.last_offline: bool | None = None
            created_clients.append(self)

        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            self.last_offline = offline
            return FetchResult(data=[], from_cache=False, timestamp=None)

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(app_module, "resolve_settings", lambda **_: settings)
    monkeypatch.setattr(app_module, "APIClient", DummyClient)

    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        ["--offline", "node", "list"],
    )

    assert result.exit_code == 0
    assert "No nodes found." in result.output
    assert responses_dir.exists(), "Cache directory was not created"
    assert created_clients, "Client was not constructed"
    client = created_clients[0]
    assert client.base_url == "https://service.example/api"
    assert client.service_token == "token-123"
    assert client.closed, "Client.close was not invoked"
    assert client.last_offline is True


def test_app_callback_profile_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_error(**_: Any) -> CLISettings:  # noqa: ANN401
        raise ProfileNotFoundError("missing profile")

    monkeypatch.setattr(app_module, "resolve_settings", raise_error)
    runner = CliRunner()
    result = runner.invoke(cli_app, ["--profile", "missing", "node", "list"])
    assert result.exit_code != 0
    assert "missing profile" in result.output


def test_app_main_invokes_typer(monkeypatch: pytest.MonkeyPatch) -> None:
    invoked: dict[str, bool] = {}

    def fake_app() -> None:
        invoked["called"] = True

    monkeypatch.setattr(app_module, "app", fake_app)
    app_module.main()
    assert invoked.get("called") is True


def test_cache_store_invalid_timestamp(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    store.ensure()
    key = store.build_key("GET", "/nodes")
    entry_path = tmp_path / "responses" / f"{key}.json"
    payload = {"timestamp": 12345, "data": {"value": 9}}
    entry_path.write_text(json.dumps(payload))

    entry = store.read(key)
    assert entry is not None
    assert entry.data == {"value": 9}
    assert isinstance(entry.timestamp, datetime)


def _build_context(
    *,
    tmp_path: Path,
    api_url: str = "https://api.example/api",
    service_token: str | None = None,
    offline: bool = False,
    client: Any,
) -> CLIContext:
    settings = CLISettings(
        api_url=api_url,
        service_token=service_token,
        profile=None,
        config_path=tmp_path / "cli.toml",
        cache_dir=tmp_path,
    )
    return CLIContext(
        settings=settings,
        client=client,
        cache=CacheStore(tmp_path),
        console=Console(record=True),
        offline=offline,
    )


def test_code_scaffold_trims_api_suffix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = CLISettings(
        api_url="https://api.demo/api",
        service_token=None,
        profile=None,
        config_path=tmp_path / "cli.toml",
        cache_dir=tmp_path,
    )

    class DummyClient:
        def __init__(
            self,
            *,
            base_url: str,
            service_token: str | None,
            cache: CacheStore,
            timeout: float = 30.0,
        ) -> None:  # noqa: ANN001
            self.base_url = base_url
            self.service_token = service_token
            self.cache = cache
            self.timeout = timeout

        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            assert path.endswith("/versions")
            return FetchResult(
                data=[{"id": "ver-1", "version": 1}],
                from_cache=False,
                timestamp=None,
            )

        def close(self) -> None:
            return None

    monkeypatch.setattr(app_module, "resolve_settings", lambda **_: settings)
    monkeypatch.setattr(app_module, "APIClient", DummyClient)

    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        [
            "--api-url",
            "https://api.demo/api",
            "--cache-dir",
            str(tmp_path),
            "code",
            "scaffold",
            "wf-1",
        ],
    )
    assert result.exit_code == 0
    assert "https://api.demo" in result.output
    assert "wf-1" in result.output


def test_code_scaffold_handles_api_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = CLISettings(
        api_url="https://api.demo",
        service_token=None,
        profile=None,
        config_path=tmp_path / "cli.toml",
        cache_dir=tmp_path,
    )

    class FailingClient:
        def __init__(
            self,
            *,
            base_url: str,
            service_token: str | None,
            cache: CacheStore,
            timeout: float = 30.0,
        ) -> None:  # noqa: ANN001
            self.base_url = base_url
            self.service_token = service_token
            self.cache = cache

        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            raise ApiRequestError("boom")

        def close(self) -> None:
            return None

    monkeypatch.setattr(app_module, "resolve_settings", lambda **_: settings)
    monkeypatch.setattr(app_module, "APIClient", FailingClient)

    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        [
            "--api-url",
            "https://api.demo",
            "--cache-dir",
            str(tmp_path),
            "code",
            "scaffold",
            "wf-2",
        ],
    )
    assert result.exit_code == 1
    assert "boom" in result.output


def test_resolve_settings_prefers_environment(tmp_path: Path) -> None:
    config_path = tmp_path / "cli.toml"
    config_path.write_text(
        """
[profiles.prod]
api_url = "https://profile.example"
service_token = "profile-token"
        """.strip()
    )
    cache_dir = tmp_path / "cache"
    env = {
        "ORCHEO_PROFILE": "prod",
        "ORCHEO_API_URL": "https://env.example",
        "ORCHEO_SERVICE_TOKEN": "env-token",
        "ORCHEO_CLI_CONFIG": str(config_path),
        "ORCHEO_CLI_CACHE": str(cache_dir),
    }

    settings = resolve_settings(
        api_url=None,
        service_token=None,
        profile=None,
        config_path=None,
        cache_dir=None,
        env=env,
    )

    assert settings.api_url == "https://env.example"
    assert settings.service_token == "env-token"
    assert settings.profile == "prod"
    assert settings.config_path == config_path
    assert settings.cache_dir == cache_dir


def test_load_profiles_skips_invalid_entries(tmp_path: Path) -> None:
    config_path = tmp_path / "cli.toml"
    config_path.write_text(
        """
[profiles]
invalid = "ignored"

[profiles.valid]
api_url = "https://valid.example"
        """.strip()
    )
    profiles = load_profiles(config_path)
    assert "invalid" not in profiles
    assert profiles["valid"].api_url == "https://valid.example"


def test_credential_list_handles_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    timestamp = datetime(2024, 1, 1, tzinfo=UTC)

    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            assert params == {"workflow_id": "wf-1"}
            data = [
                {
                    "id": "cred-1",
                    "name": "alpha",
                    "provider": "http",
                    "access": "private",
                    "status": "ok",
                },
                "invalid",
            ]
            return FetchResult(data=data, from_cache=True, timestamp=timestamp)

    context = _build_context(
        tmp_path=tmp_path,
        client=DummyClient(),
        offline=True,
    )
    monkeypatch.setattr("orcheo_sdk.cli.credentials.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(
        credential_app,
        ["list", "--workflow-id", "wf-1"],
    )
    assert result.exit_code == 0
    output = context.console.export_text()
    assert "alpha" in output
    assert "Served from cache" in output


def test_credential_list_offline_cache_miss(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            raise OfflineCacheMissError("no cache")

    context = _build_context(tmp_path=tmp_path, client=DummyClient(), offline=True)
    monkeypatch.setattr("orcheo_sdk.cli.credentials.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(credential_app, ["list"])
    assert result.exit_code == 1
    assert "no cache" in result.output


def test_credential_list_api_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            raise ApiRequestError("failure")

    context = _build_context(tmp_path=tmp_path, client=DummyClient())
    monkeypatch.setattr("orcheo_sdk.cli.credentials.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(credential_app, ["list"])
    assert result.exit_code == 1
    assert "failure" in result.output


def test_credential_list_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            return FetchResult(data=[], from_cache=False, timestamp=None)

    context = _build_context(tmp_path=tmp_path, client=DummyClient())
    monkeypatch.setattr("orcheo_sdk.cli.credentials.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(credential_app, ["list"])
    assert result.exit_code == 0
    assert "No credentials found" in result.output


def test_credential_reference_not_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            return FetchResult(
                data=[{"name": "other"}], from_cache=False, timestamp=None
            )

    context = _build_context(tmp_path=tmp_path, client=DummyClient())
    monkeypatch.setattr("orcheo_sdk.cli.credentials.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(credential_app, ["reference", "missing"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_credential_reference_cache_notice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    timestamp = datetime(2024, 4, 4, tzinfo=UTC)

    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            return FetchResult(
                data=[{"id": "cred-5", "name": "alpha"}],
                from_cache=True,
                timestamp=timestamp,
            )

    context = _build_context(tmp_path=tmp_path, client=DummyClient(), offline=True)
    monkeypatch.setattr("orcheo_sdk.cli.credentials.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(credential_app, ["reference", "cred-5"])
    assert result.exit_code == 0
    assert "Served from cache" in context.console.export_text()


def test_credential_reference_offline_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            raise OfflineCacheMissError("reference cache missing")

    context = _build_context(tmp_path=tmp_path, client=DummyClient(), offline=True)
    monkeypatch.setattr("orcheo_sdk.cli.credentials.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(credential_app, ["reference", "cred"])
    assert result.exit_code == 1
    assert "reference cache missing" in result.output


def test_credential_reference_api_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            raise ApiRequestError("reference failed")

    context = _build_context(tmp_path=tmp_path, client=DummyClient())
    monkeypatch.setattr("orcheo_sdk.cli.credentials.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(credential_app, ["reference", "cred"])
    assert result.exit_code == 1
    assert "reference failed" in result.output


def test_credential_create_parses_scopes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, Any] = {}

    class DummyClient:
        def post_json(
            self, path: str, *, params=None, json=None, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            captured.update(json or {})
            return FetchResult(data=json or {}, from_cache=False, timestamp=None)

    context = _build_context(tmp_path=tmp_path, client=DummyClient())
    monkeypatch.setattr("orcheo_sdk.cli.credentials.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(
        credential_app,
        [
            "create",
            "--name",
            "demo",
            "--provider",
            "http",
            "--secret",
            "sekrit",
            "--scopes",
            "read, write , ,admin",
        ],
        input="sekrit\n",
    )
    assert result.exit_code == 0
    assert captured["scopes"] == ["read", "write", "admin"]


def test_credential_create_api_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def post_json(
            self, path: str, *, params=None, json=None, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            raise ApiRequestError("create failed")

    context = _build_context(tmp_path=tmp_path, client=DummyClient())
    monkeypatch.setattr("orcheo_sdk.cli.credentials.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(
        credential_app,
        [
            "create",
            "--name",
            "demo",
            "--provider",
            "http",
            "--secret",
            "sekrit",
        ],
        input="sekrit\n",
    )
    assert result.exit_code == 1
    assert "create failed" in result.output


def test_credential_delete_uses_workflow_scope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    recorded: dict[str, Any] = {}

    class DummyClient:
        def fetch_json(
            self,
            method: str,
            path: str,
            *,
            params=None,
            json=None,
            offline=False,
            description="resource",
        ) -> FetchResult:  # noqa: ANN001
            recorded.update({"method": method, "path": path, "params": params})
            return FetchResult(data=None, from_cache=False, timestamp=None)

    context = _build_context(tmp_path=tmp_path, client=DummyClient())
    monkeypatch.setattr("orcheo_sdk.cli.credentials.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(
        credential_app,
        ["delete", "cred-1", "--workflow-id", "wf-9"],
    )
    assert result.exit_code == 0
    assert recorded == {
        "method": "DELETE",
        "path": "/credentials/cred-1",
        "params": {"workflow_id": "wf-9"},
    }


def test_credential_delete_api_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def fetch_json(
            self,
            method: str,
            path: str,
            *,
            params=None,
            json=None,
            offline=False,
            description="resource",
        ) -> FetchResult:  # noqa: ANN001
            raise ApiRequestError("delete failed")

    context = _build_context(tmp_path=tmp_path, client=DummyClient())
    monkeypatch.setattr("orcheo_sdk.cli.credentials.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(credential_app, ["delete", "cred-2"])
    assert result.exit_code == 1
    assert "delete failed" in result.output


def test_find_credential_helper() -> None:
    entries = [
        {"id": "cred-1", "name": "Alpha"},
        {"id": "cred-2", "name": "beta"},
        "invalid",
    ]
    assert _find_credential(entries, "cred-1") == entries[0]
    assert _find_credential(entries, "Beta") == entries[1]
    assert _find_credential(entries, "missing") is None


def test_node_list_offline_cache_miss(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            raise OfflineCacheMissError("no node cache")

    context = _build_context(tmp_path=tmp_path, client=DummyClient(), offline=True)
    monkeypatch.setattr("orcheo_sdk.cli.nodes.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(node_app, ["list"])
    assert result.exit_code == 1
    assert "no node cache" in result.output


def test_node_list_filters_and_skip_invalid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    recorded: dict[str, Any] = {}

    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            recorded.update(params or {})
            data = [
                {
                    "name": "http_request",
                    "type": "http",
                    "version": "1",
                    "category": "net",
                    "tags": ["http"],
                },
                "invalid",
            ]
            return FetchResult(data=data, from_cache=False, timestamp=None)

    context = _build_context(tmp_path=tmp_path, client=DummyClient(), offline=False)
    monkeypatch.setattr("orcheo_sdk.cli.nodes.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(node_app, ["list", "--tag", "http", "--category", "network"])
    assert result.exit_code == 0
    assert recorded == {"tag": "http", "category": "network"}
    assert "http_request" in result.output
    assert "http" in result.output
    assert "invalid" not in result.output


def test_node_list_api_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            raise ApiRequestError("node failure")

    context = _build_context(tmp_path=tmp_path, client=DummyClient())
    monkeypatch.setattr("orcheo_sdk.cli.nodes.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(node_app, ["list"])
    assert result.exit_code == 1
    assert "node failure" in result.output


def test_node_list_without_tags(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            data = [
                {
                    "name": "simple",
                    "type": "utility",
                    "version": "1",
                    "category": "general",
                }
            ]
            return FetchResult(data=data, from_cache=False, timestamp=None)

    context = _build_context(tmp_path=tmp_path, client=DummyClient())
    monkeypatch.setattr("orcheo_sdk.cli.nodes.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(node_app, ["list"])
    assert result.exit_code == 0
    assert "simple" in result.output


def test_node_show_uses_cache_notice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    timestamp = datetime(2024, 2, 2, tzinfo=UTC)

    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            payload = {
                "name": "simple",
                "type": "tool",
                "version": "1",
                "credentials": [
                    {"name": "cred", "description": "desc"},
                    "invalid",
                ],
            }
            return FetchResult(data=payload, from_cache=True, timestamp=timestamp)

    context = _build_context(tmp_path=tmp_path, client=DummyClient(), offline=True)
    monkeypatch.setattr("orcheo_sdk.cli.nodes.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(node_app, ["show", "simple"])
    assert result.exit_code == 0
    output = context.console.export_text()
    assert "Served from cache" in output
    assert "Credential Requirements" in output


def test_node_show_offline_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            raise OfflineCacheMissError("no detail cache")

    context = _build_context(tmp_path=tmp_path, client=DummyClient(), offline=True)
    monkeypatch.setattr("orcheo_sdk.cli.nodes.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(node_app, ["show", "sample"])
    assert result.exit_code == 1
    assert "no detail cache" in result.output


def test_node_show_api_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            raise ApiRequestError("node detail failed")

    context = _build_context(tmp_path=tmp_path, client=DummyClient())
    monkeypatch.setattr("orcheo_sdk.cli.nodes.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(node_app, ["show", "sample"])
    assert result.exit_code == 1
    assert "node detail failed" in result.output


def test_node_show_without_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            payload = {
                "name": "bare",
                "type": "tool",
                "version": "1",
                "credentials": [],
            }
            return FetchResult(data=payload, from_cache=False, timestamp=None)

    context = _build_context(tmp_path=tmp_path, client=DummyClient())
    monkeypatch.setattr("orcheo_sdk.cli.nodes.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(node_app, ["show", "bare"])
    assert result.exit_code == 0
    assert "Credential Requirements" not in result.output


def test_schema_rows_skips_non_dict() -> None:
    rows = _schema_rows(
        [
            {"name": "x", "type": "int", "required": True, "description": "num"},
            "invalid",
        ]
    )
    assert rows == [("x", "int", "True", "num")]


def test_show_cache_notice_ignores_missing_timestamp(tmp_path: Path) -> None:
    context = _build_context(
        tmp_path=tmp_path,
        client=object(),  # type: ignore[arg-type]
    )
    show_cache_notice(context, None)
    assert "Served from cache" not in context.console.export_text()


def test_graph_to_mermaid_sanitises_identifiers() -> None:
    graph = {
        "nodes": [
            {"name": " 1st node", "type": "trigger"},
            {"name": "B&C", "type": "task"},
        ],
        "edges": [[" 1st node", "B&C"], ["invalid"]],
    }
    mermaid = graph_to_mermaid(graph)
    assert "_1st_node" in mermaid
    assert "B_C" in mermaid
    assert "invalid" not in mermaid.splitlines()[-1]


def test_graph_to_mermaid_invalid_payload() -> None:
    graph = {"nodes": {}, "edges": []}
    mermaid = graph_to_mermaid(graph)
    assert "Invalid" in mermaid


def test_graph_to_mermaid_skips_non_dict_node() -> None:
    graph = {"nodes": [{"name": "A"}, "bad"], "edges": []}
    mermaid = graph_to_mermaid(graph)
    assert "bad" not in mermaid


def test_workflow_list_offline_cache_miss(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            raise OfflineCacheMissError("workflow cache missing")

    context = _build_context(tmp_path=tmp_path, client=DummyClient(), offline=True)
    monkeypatch.setattr("orcheo_sdk.cli.workflows.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(workflow_app, ["list"])
    assert result.exit_code == 1
    assert "workflow cache missing" in result.output


def test_workflow_list_api_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            raise ApiRequestError("list failed")

    context = _build_context(tmp_path=tmp_path, client=DummyClient())
    monkeypatch.setattr("orcheo_sdk.cli.workflows.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(workflow_app, ["list"])
    assert result.exit_code == 1
    assert "list failed" in result.output


def test_workflow_list_cached_notice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    timestamp = datetime(2024, 5, 5, tzinfo=UTC)

    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            data = [
                {
                    "id": "wf-1",
                    "name": "Flow",
                    "slug": "flow",
                    "updated_at": "2024-05-05T00:00:00+00:00",
                }
            ]
            return FetchResult(data=data, from_cache=True, timestamp=timestamp)

    context = _build_context(tmp_path=tmp_path, client=DummyClient(), offline=True)
    monkeypatch.setattr("orcheo_sdk.cli.workflows.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(workflow_app, ["list"])
    assert result.exit_code == 0
    assert "Served from cache" in context.console.export_text()


def test_workflow_list_handles_invalid_entries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            return FetchResult(data=["invalid"], from_cache=False, timestamp=None)

    context = _build_context(tmp_path=tmp_path, client=DummyClient())
    monkeypatch.setattr("orcheo_sdk.cli.workflows.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(workflow_app, ["list"])
    assert result.exit_code == 0
    assert "No workflows found" in result.output


def test_workflow_show_with_cached_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    timestamp = datetime(2024, 3, 3, tzinfo=UTC)

    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            if path.endswith("/runs"):
                data = [
                    {
                        "id": "run-1",
                        "status": "succeeded",
                        "created_at": "2024-03-02T10:00:00+00:00",
                        "completed_at": "2024-03-02T10:05:00+00:00",
                    }
                ]
                return FetchResult(data=data, from_cache=False, timestamp=None)
            if path.endswith("/versions"):
                data = [
                    {
                        "id": "ver-2",
                        "version": 2,
                        "created_at": "2024-03-01T12:00:00+00:00",
                        "created_by": "tester",
                        "graph": {
                            "nodes": [
                                {"name": "start", "type": "trigger"},
                                {"name": "end", "type": "action"},
                            ],
                            "edges": [["start", "end"]],
                        },
                    }
                ]
                return FetchResult(data=data, from_cache=False, timestamp=None)
            if path.endswith("/workflow-1"):
                data = {
                    "id": "workflow-1",
                    "name": "Example",
                    "slug": "example",
                    "description": "Demo",
                    "tags": ["demo"],
                    "updated_at": "2024-03-01T00:00:00+00:00",
                }
                return FetchResult(data=data, from_cache=True, timestamp=timestamp)
            raise AssertionError(path)

    context = _build_context(tmp_path=tmp_path, client=DummyClient(), offline=False)
    monkeypatch.setattr("orcheo_sdk.cli.workflows.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(workflow_app, ["show", "workflow-1"])
    assert result.exit_code == 0
    output = context.console.export_text()
    assert "flowchart TD" in output
    assert "Recent Runs" in output
    assert "Served from cache" in output
    assert "Tags" in output


def test_workflow_show_offline_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            raise OfflineCacheMissError("no workflow cache")

    context = _build_context(tmp_path=tmp_path, client=DummyClient(), offline=True)
    monkeypatch.setattr("orcheo_sdk.cli.workflows.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(workflow_app, ["show", "wf-err"])
    assert result.exit_code == 1
    assert "no workflow cache" in result.output


def test_workflow_show_without_tags_and_versions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            if path.endswith("/versions"):
                return FetchResult(data=[], from_cache=False, timestamp=None)
            if path.endswith("/runs"):
                return FetchResult(data=[], from_cache=False, timestamp=None)
            return FetchResult(
                data={"id": "wf", "name": "WF", "slug": "wf", "tags": "not-a-list"},
                from_cache=False,
                timestamp=None,
            )

    context = _build_context(tmp_path=tmp_path, client=DummyClient())
    monkeypatch.setattr("orcheo_sdk.cli.workflows.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(workflow_app, ["show", "wf"])
    assert result.exit_code == 0
    output = context.console.export_text()
    assert "Workflow" in output
    assert "Versions" not in output
    assert "Recent Runs" not in output


def test_workflow_show_versions_without_graph(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            if path.endswith("/versions"):
                data = [{"id": "ver", "version": 1, "graph": "not-dict"}]
                return FetchResult(data=data, from_cache=False, timestamp=None)
            return FetchResult(data={}, from_cache=False, timestamp=None)

    context = _build_context(tmp_path=tmp_path, client=DummyClient())
    monkeypatch.setattr("orcheo_sdk.cli.workflows.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(workflow_app, ["show", "wf"])
    assert result.exit_code == 0
    output = context.console.export_text()
    assert "Latest Graph" not in output


def test_workflow_show_versions_latest_not_dict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            if path.endswith("/runs"):
                return FetchResult(data=[], from_cache=False, timestamp=None)
            return FetchResult(
                data={
                    "id": "wf",
                    "name": "Workflow",
                    "slug": "wf",
                    "description": "Demo",
                },
                from_cache=False,
                timestamp=None,
            )

    class RowLike:
        def __init__(self, payload: dict[str, Any]) -> None:
            self._payload = payload

        def get(self, key: str, default: Any = "") -> Any:
            return self._payload.get(key, default)

    context = _build_context(tmp_path=tmp_path, client=DummyClient())

    def fake_fetch_versions(context: CLIContext, workflow_id: str) -> list[RowLike]:
        assert context is not None  # exercise argument usage
        assert workflow_id == "wf"
        return [
            RowLike(
                {
                    "version": 1,
                    "id": "ver-1",
                    "created_at": "2024-01-01T00:00:00+00:00",
                    "created_by": "tester",
                    "graph": {"nodes": []},
                }
            )
        ]

    monkeypatch.setattr("orcheo_sdk.cli.workflows.get_context", lambda _: context)
    monkeypatch.setattr("orcheo_sdk.cli.workflows._fetch_versions", fake_fetch_versions)

    runner = CliRunner()
    result = runner.invoke(workflow_app, ["show", "wf"])
    assert result.exit_code == 0
    output = context.console.export_text()
    assert "Latest Graph" not in output


def test_workflow_show_versions_all_invalid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            if path.endswith("/versions"):
                return FetchResult(data=["bad"], from_cache=False, timestamp=None)
            return FetchResult(data={}, from_cache=False, timestamp=None)

    context = _build_context(tmp_path=tmp_path, client=DummyClient())
    monkeypatch.setattr("orcheo_sdk.cli.workflows.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(workflow_app, ["show", "wf"])
    assert result.exit_code == 0
    output = context.console.export_text()
    assert "Latest Graph" not in output


def test_workflow_show_api_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            if path.endswith("/workflows/bad"):
                raise ApiRequestError("workflow failed")
            return FetchResult(data={}, from_cache=False, timestamp=None)

    context = _build_context(tmp_path=tmp_path, client=DummyClient())
    monkeypatch.setattr("orcheo_sdk.cli.workflows.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(workflow_app, ["show", "bad"])
    assert result.exit_code == 1
    assert "workflow failed" in result.output


def test_workflow_run_requires_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            raise OfflineCacheMissError("no versions")

        def post_json(
            self, path: str, *, params=None, json=None, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            raise AssertionError("post_json should not be called")

    context = _build_context(tmp_path=tmp_path, client=DummyClient(), offline=True)
    monkeypatch.setattr("orcheo_sdk.cli.workflows.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(workflow_app, ["run", "workflow-2"])
    assert result.exit_code == 1
    assert "Unable to determine workflow version" in result.output


def test_workflow_run_with_version_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            raise AssertionError("get_json should not be called")

        def post_json(
            self, path: str, *, params=None, json=None, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            return FetchResult(data=json or {}, from_cache=False, timestamp=None)

    context = _build_context(tmp_path=tmp_path, client=DummyClient(), offline=False)
    monkeypatch.setattr("orcheo_sdk.cli.workflows.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(
        workflow_app,
        ["run", "workflow", "--version-id", "ver-1", "--inputs", "{}"],
    )
    assert result.exit_code == 0
    assert "Run ID" in result.output


def test_workflow_run_api_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            return FetchResult(
                data=[{"id": "ver-1", "version": 1}], from_cache=False, timestamp=None
            )

        def post_json(
            self, path: str, *, params=None, json=None, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            raise ApiRequestError("run failed")

    context = _build_context(tmp_path=tmp_path, client=DummyClient(), offline=False)
    monkeypatch.setattr("orcheo_sdk.cli.workflows.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(workflow_app, ["run", "workflow-err"])
    assert result.exit_code == 1
    assert "run failed" in result.output


def test_workflow_run_posts_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    versions = [
        {"id": "ver-1", "version": 1},
        {"id": "ver-2", "version": 2},
    ]
    captured: dict[str, Any] = {}

    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            if path.endswith("/versions"):
                return FetchResult(data=versions, from_cache=False, timestamp=None)
            raise AssertionError(path)

        def post_json(
            self, path: str, *, params=None, json=None, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            captured.update(json or {})
            return FetchResult(data=json or {}, from_cache=False, timestamp=None)

    context = _build_context(tmp_path=tmp_path, client=DummyClient(), offline=False)
    monkeypatch.setattr("orcheo_sdk.cli.workflows.get_context", lambda _: context)

    runner = CliRunner()
    result = runner.invoke(
        workflow_app,
        ["run", "workflow-3", "--inputs", '{"foo": "bar"}', "--actor", "cli-user"],
    )
    assert result.exit_code == 0
    assert captured["workflow_version_id"] == "ver-2"
    assert captured["triggered_by"] == "cli-user"
    assert captured["input_payload"] == {"foo": "bar"}


def test_fetch_versions_handles_api_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            raise ApiRequestError("versions failed")

    context = _build_context(tmp_path=tmp_path, client=DummyClient())

    def fake_abort(ctx: CLIContext, exc: ApiRequestError) -> None:
        raise RuntimeError(str(exc))

    monkeypatch.setattr("orcheo_sdk.cli.workflows.abort_with_error", fake_abort)
    from orcheo_sdk.cli.workflows import _fetch_versions

    with pytest.raises(RuntimeError, match="versions failed"):
        _fetch_versions(context, "wf-err")


def test_fetch_runs_offline_error(tmp_path: Path) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            raise OfflineCacheMissError("offline")

    context = _build_context(tmp_path=tmp_path, client=DummyClient(), offline=True)
    from orcheo_sdk.cli.workflows import _fetch_runs

    runs = _fetch_runs(context, "wf")
    assert runs == []


def test_fetch_runs_api_error(tmp_path: Path) -> None:
    class DummyClient:
        def get_json(
            self, path: str, *, params=None, offline=False, description="resource"
        ) -> FetchResult:  # noqa: ANN001
            raise ApiRequestError("runs failed")

    context = _build_context(tmp_path=tmp_path, client=DummyClient())
    from orcheo_sdk.cli.workflows import _fetch_runs

    runs = _fetch_runs(context, "wf")
    assert runs == []


def test_format_datetime_helpers() -> None:
    assert _format_datetime("2024-01-01T00:00:00Z").startswith("2024-01-01T00:00:00+")
    now = datetime(2024, 1, 1)
    assert _format_datetime(now) == now.isoformat()
    assert _format_datetime(123) == ""
