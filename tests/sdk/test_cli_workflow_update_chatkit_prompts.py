"""CLI tests for workflow ChatKit prompt updates."""

from __future__ import annotations
import json
import httpx
import respx
from typer.testing import CliRunner
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.main import app


def test_workflow_update_chatkit_prompts(
    runner: CliRunner, env: dict[str, str]
) -> None:
    with respx.mock(assert_all_called=True) as router:
        update_route = router.put("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "wf-1",
                    "name": "Workflow",
                    "slug": "workflow",
                    "description": None,
                    "tags": [],
                    "is_archived": False,
                    "is_public": False,
                    "require_login": False,
                    "published_at": None,
                    "published_by": None,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "audit_log": [],
                    "chatkit": {
                        "start_screen_prompts": [
                            {
                                "label": "Summarize the latest run",
                                "prompt": "Summarize the latest run for me.",
                                "icon": "search",
                            }
                        ]
                    },
                },
            )
        )

        result = runner.invoke(
            app,
            [
                "workflow",
                "update",
                "wf-1",
                "--chatkit-prompts",
                '[{"label":"Summarize the latest run","prompt":"Summarize the latest run for me.","icon":"search"}]',  # noqa: E501
            ],
            env=env,
        )

    assert result.exit_code == 0
    request_payload = json.loads(update_route.calls[0].request.content)
    assert request_payload["chatkit"] == {
        "start_screen_prompts": [
            {
                "label": "Summarize the latest run",
                "prompt": "Summarize the latest run for me.",
                "icon": "search",
            }
        ]
    }
    assert request_payload["actor"] == "cli"


def test_workflow_update_clear_chatkit_prompts(
    runner: CliRunner, env: dict[str, str]
) -> None:
    with respx.mock(assert_all_called=True) as router:
        update_route = router.put("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "wf-1",
                    "name": "Workflow",
                    "slug": "workflow",
                    "description": None,
                    "tags": [],
                    "is_archived": False,
                    "is_public": False,
                    "require_login": False,
                    "published_at": None,
                    "published_by": None,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "audit_log": [],
                    "chatkit": {"start_screen_prompts": None},
                },
            )
        )

        result = runner.invoke(
            app,
            ["workflow", "update", "wf-1", "--clear-chatkit-prompts"],
            env=env,
        )

    assert result.exit_code == 0
    request_payload = json.loads(update_route.calls[0].request.content)
    assert request_payload["chatkit"] == {"start_screen_prompts": None}


def test_workflow_update_rejects_clear_and_chatkit_prompts_together(
    runner: CliRunner, env: dict[str, str]
) -> None:
    result = runner.invoke(
        app,
        [
            "workflow",
            "update",
            "wf-1",
            "--chatkit-prompts",
            '["Summarize the latest run"]',
            "--clear-chatkit-prompts",
        ],
        env=env,
    )

    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "Use either --clear-chatkit-prompts" in str(result.exception)


def test_workflow_update_chatkit_models(runner: CliRunner, env: dict[str, str]) -> None:
    with respx.mock(assert_all_called=True) as router:
        update_route = router.put("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "wf-1",
                    "name": "Workflow",
                    "slug": "workflow",
                    "description": None,
                    "tags": [],
                    "is_archived": False,
                    "is_public": False,
                    "require_login": False,
                    "published_at": None,
                    "published_by": None,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "audit_log": [],
                    "chatkit": {
                        "supported_models": [
                            {
                                "id": "openai:gpt-5",
                                "label": "GPT-5",
                                "default": True,
                            }
                        ]
                    },
                },
            )
        )

        result = runner.invoke(
            app,
            [
                "workflow",
                "update",
                "wf-1",
                "--chatkit-models",
                '[{"id":"openai:gpt-5","label":"GPT-5","default":true}]',
            ],
            env=env,
        )

    assert result.exit_code == 0
    request_payload = json.loads(update_route.calls[0].request.content)
    assert request_payload["chatkit"] == {
        "supported_models": [
            {
                "id": "openai:gpt-5",
                "label": "GPT-5",
                "default": True,
            }
        ]
    }
    assert request_payload["actor"] == "cli"


def test_workflow_update_clear_chatkit_models(
    runner: CliRunner, env: dict[str, str]
) -> None:
    with respx.mock(assert_all_called=True) as router:
        update_route = router.put("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "wf-1",
                    "name": "Workflow",
                    "slug": "workflow",
                    "description": None,
                    "tags": [],
                    "is_archived": False,
                    "is_public": False,
                    "require_login": False,
                    "published_at": None,
                    "published_by": None,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "audit_log": [],
                    "chatkit": {"supported_models": None},
                },
            )
        )

        result = runner.invoke(
            app,
            ["workflow", "update", "wf-1", "--clear-chatkit-models"],
            env=env,
        )

    assert result.exit_code == 0
    request_payload = json.loads(update_route.calls[0].request.content)
    assert request_payload["chatkit"] == {"supported_models": None}


def test_workflow_update_rejects_clear_and_chatkit_models_together(
    runner: CliRunner, env: dict[str, str]
) -> None:
    result = runner.invoke(
        app,
        [
            "workflow",
            "update",
            "wf-1",
            "--chatkit-models",
            '["openai:gpt-5"]',
            "--clear-chatkit-models",
        ],
        env=env,
    )

    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "Use either --clear-chatkit-models" in str(result.exception)
