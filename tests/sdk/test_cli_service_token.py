"""Tests for the CLI service token commands."""

from __future__ import annotations
from pathlib import Path
import httpx
import pytest
import respx
from orcheo_sdk.cli.main import app
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
        "ORCHEO_SERVICE_TOKEN": "admin-token",
        "ORCHEO_CONFIG_DIR": str(config_dir),
        "ORCHEO_CACHE_DIR": str(cache_dir),
        "NO_COLOR": "1",
    }


def test_token_create_minimal(runner: CliRunner, env: dict[str, str]) -> None:
    """Test creating a token with minimal options."""
    response_data = {
        "identifier": "token-123",
        "secret": "secret-abc-xyz",
    }

    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/admin/service-tokens").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = runner.invoke(app, ["token", "create"], env=env)

    assert result.exit_code == 0
    assert "token-123" in result.stdout
    assert "secret-abc-xyz" in result.stdout
    assert "Store this secret securely" in result.stdout


def test_token_create_with_identifier(runner: CliRunner, env: dict[str, str]) -> None:
    """Test creating a token with custom identifier."""
    response_data = {
        "identifier": "my-custom-token",
        "secret": "secret-123",
    }

    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/admin/service-tokens").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = runner.invoke(
            app, ["token", "create", "--id", "my-custom-token"], env=env
        )

    assert result.exit_code == 0
    assert "my-custom-token" in result.stdout


def test_token_create_with_scopes(runner: CliRunner, env: dict[str, str]) -> None:
    """Test creating a token with scopes."""
    response_data = {
        "identifier": "scoped-token",
        "secret": "secret-123",
        "scopes": ["read:workflows", "write:workflows"],
    }

    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/admin/service-tokens").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = runner.invoke(
            app,
            [
                "token",
                "create",
                "--scope",
                "read:workflows",
                "--scope",
                "write:workflows",
            ],
            env=env,
        )

    assert result.exit_code == 0
    assert "read:workflows" in result.stdout
    assert "write:workflows" in result.stdout


def test_token_create_with_workspaces(runner: CliRunner, env: dict[str, str]) -> None:
    """Test creating a token with workspace restrictions."""
    response_data = {
        "identifier": "workspace-token",
        "secret": "secret-123",
        "workspace_ids": ["ws-1", "ws-2"],
    }

    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/admin/service-tokens").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = runner.invoke(
            app,
            ["token", "create", "--workspace", "ws-1", "--workspace", "ws-2"],
            env=env,
        )

    assert result.exit_code == 0
    assert "ws-1" in result.stdout
    assert "ws-2" in result.stdout


def test_token_create_with_expiration(runner: CliRunner, env: dict[str, str]) -> None:
    """Test creating a token with expiration."""
    response_data = {
        "identifier": "expiring-token",
        "secret": "secret-123",
        "expires_at": "2024-12-31T23:59:59Z",
    }

    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/admin/service-tokens").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = runner.invoke(
            app, ["token", "create", "--expires-in", "3600"], env=env
        )

    assert result.exit_code == 0
    assert "2024-12-31" in result.stdout


def test_token_create_with_all_options(runner: CliRunner, env: dict[str, str]) -> None:
    """Test creating a token with all options."""
    response_data = {
        "identifier": "full-token",
        "secret": "secret-123",
        "scopes": ["read:all"],
        "workspace_ids": ["ws-1"],
        "expires_at": "2024-12-31T23:59:59Z",
    }

    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/admin/service-tokens").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = runner.invoke(
            app,
            [
                "token",
                "create",
                "--id",
                "full-token",
                "--scope",
                "read:all",
                "--workspace",
                "ws-1",
                "--expires-in",
                "3600",
            ],
            env=env,
        )

    assert result.exit_code == 0
    assert "full-token" in result.stdout
    assert "secret-123" in result.stdout
    assert "read:all" in result.stdout
    assert "ws-1" in result.stdout


def test_token_list_empty(runner: CliRunner, env: dict[str, str]) -> None:
    """Test listing tokens when none exist."""
    response_data = {"tokens": [], "total": 0}

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/admin/service-tokens").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = runner.invoke(app, ["token", "list"], env=env)

    assert result.exit_code == 0
    assert "No service tokens found" in result.stdout


def test_token_list_with_tokens(runner: CliRunner, env: dict[str, str]) -> None:
    """Test listing tokens."""
    response_data = {
        "tokens": [
            {
                "identifier": "token-1",
                "scopes": ["read:workflows"],
                "workspace_ids": ["ws-1"],
                "issued_at": "2024-11-01T10:00:00Z",
                "expires_at": "2024-12-01T10:00:00Z",
            },
            {
                "identifier": "token-2",
                "scopes": [],
                "workspace_ids": [],
                "issued_at": "2024-11-02T10:00:00Z",
            },
        ],
        "total": 2,
    }

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/admin/service-tokens").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = runner.invoke(app, ["token", "list"], env=env)

    assert result.exit_code == 0
    assert "Service Tokens" in result.stdout
    assert "token-1" in result.stdout
    assert "token-2" in result.stdout
    assert "read:workflo" in result.stdout  # May be truncated in table


def test_token_list_with_revoked_token(runner: CliRunner, env: dict[str, str]) -> None:
    """Test listing tokens includes revoked status."""
    response_data = {
        "tokens": [
            {
                "identifier": "revoked-token",
                "scopes": [],
                "workspace_ids": [],
                "issued_at": "2024-11-01T10:00:00Z",
                "revoked_at": "2024-11-02T10:00:00Z",
            }
        ],
        "total": 1,
    }

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/admin/service-tokens").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = runner.invoke(app, ["token", "list"], env=env)

    assert result.exit_code == 0
    assert "revoked-token" in result.stdout
    assert "Revoked" in result.stdout


def test_token_list_with_rotated_token(runner: CliRunner, env: dict[str, str]) -> None:
    """Test listing tokens includes rotated status."""
    response_data = {
        "tokens": [
            {
                "identifier": "rotated-token",
                "scopes": [],
                "workspace_ids": [],
                "issued_at": "2024-11-01T10:00:00Z",
                "rotated_to": "new-token-id",
            }
        ],
        "total": 1,
    }

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/admin/service-tokens").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = runner.invoke(app, ["token", "list"], env=env)

    assert result.exit_code == 0
    assert "rotated-token" in result.stdout
    assert "Rotated" in result.stdout


def test_token_show_basic(runner: CliRunner, env: dict[str, str]) -> None:
    """Test showing token details."""
    response_data = {
        "identifier": "token-123",
        "scopes": ["read:workflows"],
        "workspace_ids": ["ws-1"],
        "issued_at": "2024-11-01T10:00:00Z",
        "expires_at": "2024-12-01T10:00:00Z",
    }

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/admin/service-tokens/token-123").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = runner.invoke(app, ["token", "show", "token-123"], env=env)

    assert result.exit_code == 0
    assert "token-123" in result.stdout
    assert "read:workflows" in result.stdout
    assert "ws-1" in result.stdout


def test_token_show_without_scopes(runner: CliRunner, env: dict[str, str]) -> None:
    """Test showing token without scopes."""
    response_data = {
        "identifier": "token-123",
        "issued_at": "2024-11-01T10:00:00Z",
    }

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/admin/service-tokens/token-123").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = runner.invoke(app, ["token", "show", "token-123"], env=env)

    assert result.exit_code == 0
    assert "token-123" in result.stdout


def test_token_show_without_expiration(runner: CliRunner, env: dict[str, str]) -> None:
    """Test showing token without expiration."""
    response_data = {
        "identifier": "token-123",
        "issued_at": "2024-11-01T10:00:00Z",
    }

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/admin/service-tokens/token-123").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = runner.invoke(app, ["token", "show", "token-123"], env=env)

    assert result.exit_code == 0
    assert "Never" in result.stdout


def test_token_show_revoked_with_reason(runner: CliRunner, env: dict[str, str]) -> None:
    """Test showing revoked token with reason."""
    response_data = {
        "identifier": "token-123",
        "issued_at": "2024-11-01T10:00:00Z",
        "revoked_at": "2024-11-02T10:00:00Z",
        "revocation_reason": "Security breach",
    }

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/admin/service-tokens/token-123").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = runner.invoke(app, ["token", "show", "token-123"], env=env)

    assert result.exit_code == 0
    assert "Security breach" in result.stdout


def test_token_show_revoked_without_reason(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test showing revoked token without reason."""
    response_data = {
        "identifier": "token-123",
        "issued_at": "2024-11-01T10:00:00Z",
        "revoked_at": "2024-11-02T10:00:00Z",
    }

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/admin/service-tokens/token-123").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = runner.invoke(app, ["token", "show", "token-123"], env=env)

    assert result.exit_code == 0
    assert "token-123" in result.stdout


def test_token_show_without_issued_at(runner: CliRunner, env: dict[str, str]) -> None:
    """Test showing token without issued_at field."""
    response_data = {
        "identifier": "token-123",
    }

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/admin/service-tokens/token-123").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = runner.invoke(app, ["token", "show", "token-123"], env=env)

    assert result.exit_code == 0
    assert "token-123" in result.stdout


def test_token_show_rotated(runner: CliRunner, env: dict[str, str]) -> None:
    """Test showing rotated token."""
    response_data = {
        "identifier": "token-123",
        "issued_at": "2024-11-01T10:00:00Z",
        "rotated_to": "new-token-456",
    }

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/admin/service-tokens/token-123").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = runner.invoke(app, ["token", "show", "token-123"], env=env)

    assert result.exit_code == 0
    assert "new-token-456" in result.stdout


def test_token_rotate_basic(runner: CliRunner, env: dict[str, str]) -> None:
    """Test rotating a token."""
    response_data = {
        "identifier": "new-token-456",
        "secret": "new-secret-xyz",
    }

    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/admin/service-tokens/token-123/rotate").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = runner.invoke(app, ["token", "rotate", "token-123"], env=env)

    assert result.exit_code == 0
    assert "new-token-456" in result.stdout
    assert "new-secret-xyz" in result.stdout
    assert "Store this secret securely" in result.stdout


def test_token_rotate_with_custom_overlap(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test rotating a token with custom overlap period."""
    response_data = {
        "identifier": "new-token-456",
        "secret": "new-secret-xyz",
    }

    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/admin/service-tokens/token-123/rotate").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = runner.invoke(
            app, ["token", "rotate", "token-123", "--overlap", "600"], env=env
        )

    assert result.exit_code == 0
    assert "new-token-456" in result.stdout


def test_token_rotate_with_expiration(runner: CliRunner, env: dict[str, str]) -> None:
    """Test rotating a token with new expiration."""
    response_data = {
        "identifier": "new-token-456",
        "secret": "new-secret-xyz",
    }

    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/admin/service-tokens/token-123/rotate").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = runner.invoke(
            app, ["token", "rotate", "token-123", "--expires-in", "7200"], env=env
        )

    assert result.exit_code == 0
    assert "new-token-456" in result.stdout


def test_token_rotate_with_message(runner: CliRunner, env: dict[str, str]) -> None:
    """Test rotating a token that returns a message."""
    response_data = {
        "identifier": "new-token-456",
        "secret": "new-secret-xyz",
        "message": "Old token will expire in 5 minutes",
    }

    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/admin/service-tokens/token-123/rotate").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = runner.invoke(app, ["token", "rotate", "token-123"], env=env)

    assert result.exit_code == 0
    assert "Old token will expire in 5 minutes" in result.stdout


def test_token_revoke(runner: CliRunner, env: dict[str, str]) -> None:
    """Test revoking a token."""
    with respx.mock(assert_all_called=True) as router:
        router.delete("http://api.test/api/admin/service-tokens/token-123").mock(
            return_value=httpx.Response(204)
        )
        result = runner.invoke(
            app,
            ["token", "revoke", "token-123", "--reason", "No longer needed"],
            env=env,
        )

    assert result.exit_code == 0
    assert "revoked successfully" in result.stdout
    assert "No longer needed" in result.stdout


def test_token_revoke_security_breach(runner: CliRunner, env: dict[str, str]) -> None:
    """Test revoking a token due to security breach."""
    with respx.mock(assert_all_called=True) as router:
        router.delete("http://api.test/api/admin/service-tokens/token-123").mock(
            return_value=httpx.Response(204)
        )
        result = runner.invoke(
            app,
            ["token", "revoke", "token-123", "-r", "Security breach detected"],
            env=env,
        )

    assert result.exit_code == 0
    assert "revoked successfully" in result.stdout
    assert "Security breach detected" in result.stdout


def test_revoke_service_token_data_with_message() -> None:
    """Test revoke_service_token_data when response contains a message field."""
    from orcheo_sdk.cli.http import ApiClient
    from orcheo_sdk.services.service_tokens import revoke_service_token_data

    with respx.mock:
        # Mock a 200 response with a custom message
        respx.delete("http://api.test/api/admin/service-tokens/token-123").mock(
            return_value=httpx.Response(
                200, json={"message": "Token revoked successfully"}
            )
        )

        client = ApiClient(
            base_url="http://api.test",
            token="test-token",
        )
        result = revoke_service_token_data(client, "token-123", "test reason")

        # Should use the message from the response
        assert result["status"] == "success"
        assert result["message"] == "Token revoked successfully"
