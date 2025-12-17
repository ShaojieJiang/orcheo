"""Tests for rotating and revoking CLI service tokens."""

from __future__ import annotations
import httpx
import respx
from typer.testing import CliRunner
from orcheo_sdk.cli.http import ApiClient
from orcheo_sdk.cli.main import app
from orcheo_sdk.services.service_tokens import revoke_service_token_data


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
    with respx.mock:
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

        assert result["status"] == "success"
        assert result["message"] == "Token revoked successfully"
