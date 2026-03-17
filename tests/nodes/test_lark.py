"""Tests for Lark nodes."""

from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.lark import LarkSendMessageNode


@pytest.mark.asyncio
async def test_lark_send_message_replies_in_thread() -> None:
    """Reply sends should use the message reply endpoint."""
    node = LarkSendMessageNode(
        name="send_lark",
        app_id="cli_app_id",
        app_secret="app_secret",
        reply_to_message_id="om_message",
        thread_id="omt_thread",
        message='Hello "Lark"',
    )

    state = State(
        messages=[],
        inputs={},
        results={
            "get_lark_tenant_token": {"json": {"tenant_access_token": "tenant_token"}}
        },
    )

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "code": 0,
        "msg": "success",
        "data": {"message_id": "om_reply"},
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("orcheo.nodes.lark.httpx.AsyncClient", return_value=mock_client):
        result = await node.run(state, RunnableConfig())

    assert result["is_error"] is False
    call_args = mock_client.post.call_args
    assert call_args.args[0].endswith("/im/v1/messages/om_message/reply")
    assert call_args.kwargs["json"]["reply_in_thread"] is True
    assert call_args.kwargs["json"]["content"] == '{"text": "Hello \\"Lark\\""}'


@pytest.mark.asyncio
async def test_lark_send_message_fetches_token_for_new_message() -> None:
    """New-message sends should fetch a tenant token when no prior result exists."""
    node = LarkSendMessageNode(
        name="send_lark",
        app_id="cli_app_id",
        app_secret="app_secret",
        receive_id="oc_chat",
        message="Hello chat",
    )

    state = State(messages=[], inputs={}, results={})

    token_response = MagicMock()
    token_response.json.return_value = {
        "code": 0,
        "msg": "success",
        "tenant_access_token": "tenant_token",
    }
    token_response.raise_for_status = MagicMock()

    send_response = MagicMock()
    send_response.json.return_value = {
        "code": 0,
        "msg": "success",
        "data": {"message_id": "om_sent"},
    }
    send_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.post = AsyncMock(side_effect=[token_response, send_response])

    with patch("orcheo.nodes.lark.httpx.AsyncClient", return_value=mock_client):
        result = await node.run(state, RunnableConfig())

    assert result["is_error"] is False
    first_call = mock_client.post.call_args_list[0]
    second_call = mock_client.post.call_args_list[1]
    assert first_call.args[0].endswith("/auth/v3/tenant_access_token/internal")
    assert second_call.args[0].endswith("/im/v1/messages")
    assert second_call.kwargs["params"] == {"receive_id_type": "chat_id"}
    assert second_call.kwargs["json"]["receive_id"] == "oc_chat"


@pytest.mark.asyncio
async def test_lark_send_message_ignores_unresolved_templates() -> None:
    """Unresolved template strings should not be treated as valid recipients."""
    node = LarkSendMessageNode(
        name="send_lark",
        app_id="cli_app_id",
        app_secret="app_secret",
        receive_id="{{results.lark_listener.reply_target.chat_id}}",
        reply_to_message_id="{{results.lark_listener.reply_target.message_id}}",
        message="Hello chat",
    )

    state = State(
        messages=[],
        inputs={},
        results={
            "get_lark_tenant_token": {"json": {"tenant_access_token": "tenant_token"}}
        },
    )

    result = await node.run(state, RunnableConfig())

    assert result == {
        "is_error": True,
        "error": "No Lark receive_id or reply_to_message_id provided",
    }
