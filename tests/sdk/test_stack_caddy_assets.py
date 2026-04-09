"""Validation coverage for bundled Caddy ingress stack assets."""

from __future__ import annotations
import shutil
import subprocess
from pathlib import Path
import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
STACK_DIR = REPO_ROOT / "deploy" / "stack"
COMPOSE_FILE = STACK_DIR / "docker-compose.yml"
CADDYFILE = STACK_DIR / "Caddyfile"
ENV_EXAMPLE = STACK_DIR / ".env.example"


def test_stack_compose_defines_public_ingress_and_debug_profiles() -> None:
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    services = compose["services"]

    assert "ports" not in services["backend"]
    assert "ports" not in services["canvas"]
    assert services["backend-debug"]["profiles"] == ["debug-ports"]
    assert services["canvas-debug"]["profiles"] == ["debug-ports"]
    assert services["caddy"]["profiles"] == ["public-ingress"]
    assert "./Caddyfile:/etc/caddy/Caddyfile:ro" in services["caddy"]["volumes"]
    assert "caddy_data:/data" in services["caddy"]["volumes"]
    assert "caddy_config:/config" in services["caddy"]["volumes"]
    assert (
        "127.0.0.1:${ORCHEO_POSTGRES_DEBUG_PORT:-5432}:5432"
        in services["postgres"]["ports"]
    )
    assert (
        "127.0.0.1:${ORCHEO_REDIS_DEBUG_PORT:-6379}:6379" in services["redis"]["ports"]
    )
    assert "caddy_data" in compose["volumes"]
    assert "caddy_config" in compose["volumes"]


def test_caddyfile_routes_canvas_api_and_websockets() -> None:
    content = CADDYFILE.read_text(encoding="utf-8")

    assert "{$ORCHEO_CADDY_SITE_ADDRESS}" in content
    assert "@backend path /api/* /ws/*" in content
    assert (
        "reverse_proxy @backend {$ORCHEO_CADDY_BACKEND_UPSTREAMS:backend:8000}"
        in content
    )
    assert "health_uri /api/system/health" in content
    assert "lb_policy round_robin" in content
    assert "reverse_proxy {$ORCHEO_CADDY_CANVAS_UPSTREAM:canvas:5173}" in content


def test_env_example_documents_public_ingress_contract() -> None:
    content = ENV_EXAMPLE.read_text(encoding="utf-8")

    assert "ORCHEO_PUBLIC_INGRESS_ENABLED=false" in content
    assert "ORCHEO_PUBLIC_HOST=" in content
    assert "ORCHEO_PUBLISH_DEBUG_PORTS=true" in content
    assert "COMPOSE_PROFILES=debug-ports" in content
    assert "ORCHEO_CADDY_BACKEND_UPSTREAMS=backend:8000" in content
    assert "VITE_ALLOWED_HOSTS=localhost,127.0.0.1" in content


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker is not available")
def test_stack_compose_config_renders_with_profiles(tmp_path: Path) -> None:
    temp_stack_dir = tmp_path / "stack"
    temp_stack_dir.mkdir()
    for source in (COMPOSE_FILE, CADDYFILE, ENV_EXAMPLE):
        target = temp_stack_dir / source.name
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    (temp_stack_dir / ".env").write_text(
        ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8"
    )

    result = subprocess.run(
        [
            "docker",
            "compose",
            "--profile",
            "debug-ports",
            "--profile",
            "public-ingress",
            "-f",
            str(temp_stack_dir / "docker-compose.yml"),
            "--project-directory",
            str(temp_stack_dir),
            "config",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=temp_stack_dir,
    )

    assert result.returncode == 0, result.stderr
