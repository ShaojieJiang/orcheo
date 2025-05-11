"""Tests for Telegram node."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from aic_flow.graph.state import State
from aic_flow.nodes.telegram import MessageTelegram


@pytest.fixture
def telegram_node():
    return MessageTelegram(
        name="telegram_node",
        token="test_token",
        chat_id="123456",
        message="Test message",
    )


@pytest.mark.asyncio
async def test_telegram_node_send_message(telegram_node):
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": {"message_id": 42}}

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value.post.return_value = mock_response

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await telegram_node.run(State(), None)

        assert result == {"message_id": 42, "status": "sent"}
        mock_client.__aenter__.return_value.post.assert_called_once_with(
            "https://api.telegram.org/bottest_token/sendMessage",
            json={
                "chat_id": "123456",
                "text": "Test message",
                "parse_mode": "MarkdownV2",
            },
        )
