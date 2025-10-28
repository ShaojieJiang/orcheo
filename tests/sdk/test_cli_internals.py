from __future__ import annotations
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
import httpx
import pytest
from orcheo_sdk.cli import app as cli_app
from orcheo_sdk.cli.api import APIClient, ApiRequestError
from orcheo_sdk.cli.cache import CacheStore
from orcheo_sdk.cli.config import CLISettings, ProfileNotFoundError, resolve_settings
from orcheo_sdk.cli.render import (
    graph_to_mermaid,
    render_kv_section,
    render_mermaid,
    render_table,
)
from orcheo_sdk.cli.state import CLIContext
from orcheo_sdk.cli.utils import get_context, show_cache_notice
from rich.console import Console
from typer.testing import CliRunner


def test_cache_store_roundtrip(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    store.ensure()
    key = store.build_key("GET", "/nodes", {"tag": "ai"})
    store.write(key, {"value": 1})
    cached = store.read(key)
    assert cached is not None
    assert cached.data == {"value": 1}


def test_api_client_offline_and_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    responses: dict[tuple[str, str], httpx.Response | Exception] = {}

    class DummyHttpxClient:
        def __init__(self, *, base_url: str, timeout: float, headers: dict[str, str]):
            self.base_url = base_url

        def request(self, method: str, path: str, params=None, json=None):
            key = (method.upper(), path)
            response = responses.get(key)
            if response is None:
                request = httpx.Request(method, f"{self.base_url}{path}")
                raise httpx.RequestError("missing", request=request)
            if isinstance(response, Exception):
                raise response
            return response

        def close(self) -> None:  # pragma: no cover - no resources to release
            return None

    monkeypatch.setattr("orcheo_sdk.cli.api.httpx.Client", DummyHttpxClient)

    cache = CacheStore(tmp_path)
    cache.ensure()
    client = APIClient(
        base_url="https://api.example/api", service_token=None, cache=cache
    )

    ok_response = httpx.Response(
        200,
        request=httpx.Request("GET", "https://api.example/api/data"),
        json={"value": 42},
    )
    responses[("GET", "/data")] = ok_response
    result = client.get_json("/data")
    assert result.data == {"value": 42}

    cached = client.get_json("/data", offline=True)
    assert cached.from_cache and cached.data == {"value": 42}

    error_response = httpx.Response(
        500,
        request=httpx.Request("GET", "https://api.example/api/data"),
    )
    responses[("GET", "/data")] = error_response
    fallback = client.get_json("/data")
    assert fallback.from_cache and fallback.data == {"value": 42}

    failing_request = httpx.Request("GET", "https://api.example/api/data")
    responses[("GET", "/data")] = httpx.RequestError("down", request=failing_request)
    recovered = client.get_json("/data")
    assert recovered.from_cache and recovered.data == {"value": 42}

    other_request = httpx.Request("GET", "https://api.example/api/other")
    responses[("GET", "/other")] = httpx.RequestError("boom", request=other_request)
    with pytest.raises(ApiRequestError):
        client.get_json("/other")


def test_config_resolve_and_profile(tmp_path: Path) -> None:
    config_path = tmp_path / "cli.toml"
    config_path.write_text(
        """
[profiles.dev]
api_url = "https://dev.example"
service_token = "dev-token"
        """.strip()
    )
    settings = resolve_settings(
        api_url=None,
        service_token=None,
        profile="dev",
        config_path=config_path,
        cache_dir=tmp_path,
        env={},
    )
    assert settings.api_url == "https://dev.example"
    assert settings.service_token == "dev-token"

    with pytest.raises(ProfileNotFoundError):
        resolve_settings(
            api_url=None,
            service_token=None,
            profile="missing",
            config_path=config_path,
            cache_dir=tmp_path,
            env={},
        )

    env_settings = resolve_settings(
        api_url=None,
        service_token=None,
        profile=None,
        config_path=config_path,
        cache_dir=tmp_path,
        env={"ORCHEO_API_URL": "https://env.example"},
    )
    assert env_settings.api_url == "https://env.example"


def test_render_helpers(tmp_path: Path) -> None:
    console = Console(record=True)
    render_table(
        console,
        title="Sample",
        columns=("Name", "Value"),
        rows=[("alpha", "beta")],
    )
    render_kv_section(
        console,
        title="Metadata",
        pairs=[("Status", "ok")],
    )
    mermaid = graph_to_mermaid(
        {
            "nodes": [{"name": "A", "type": "start"}, {"name": "B", "type": "end"}],
            "edges": [["A", "B"]],
        }
    )
    render_mermaid(console, title="Graph", mermaid=mermaid)
    output = console.export_text()
    assert "flowchart" in output
    assert "Status" in output


def test_utils_helpers(tmp_path: Path) -> None:
    dummy_ctx = SimpleNamespace(ensure_object=lambda _: object())
    with pytest.raises(RuntimeError):
        get_context(dummy_ctx)  # type: ignore[arg-type]

    console = Console(record=True)
    settings = CLISettings(
        api_url="https://api.example",
        service_token="token",
        profile="dev",
        config_path=tmp_path,
        cache_dir=tmp_path,
    )
    context = CLIContext(
        settings=settings,
        client=object(),  # type: ignore[arg-type]
        cache=CacheStore(tmp_path),
        console=console,
    )
    show_cache_notice(context, datetime.now(tz=UTC))
    assert "Served from cache" in console.export_text()


def test_code_scaffold_requires_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    responses: dict[tuple[str, str], httpx.Response] = {}

    class DummyHttpxClient:
        def __init__(self, *, base_url: str, timeout: float, headers: dict[str, str]):
            self.base_url = base_url

        def request(self, method: str, path: str, params=None, json=None):
            key = (method.upper(), path)
            response = responses.get(key)
            if response is None:
                request = httpx.Request(method, f"{self.base_url}{path}")
                raise httpx.RequestError("missing", request=request)
            return response

        def close(self) -> None:  # pragma: no cover - no resources to release
            return None

    monkeypatch.setattr("orcheo_sdk.cli.api.httpx.Client", DummyHttpxClient)

    workflow_id = "no-versions"
    responses[("GET", f"/workflows/{workflow_id}/versions")] = httpx.Response(
        200,
        request=httpx.Request(
            "GET", f"https://api.orcheo.test/api/workflows/{workflow_id}/versions"
        ),
        json=[],
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        [
            "--api-url",
            "https://api.orcheo.test",
            "--cache-dir",
            str(tmp_path),
            "code",
            "scaffold",
            workflow_id,
        ],
    )
    assert result.exit_code == 1
    assert "deploy a version" in result.output


def _api_url(base: str) -> str:
    return f"{base.rstrip('/')}/api"
