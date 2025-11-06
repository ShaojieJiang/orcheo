"""Credential CLI command tests."""

from __future__ import annotations
import json
import httpx
import respx
from orcheo_sdk.cli.main import app
from typer.testing import CliRunner


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
