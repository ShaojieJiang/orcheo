"""Tests for Telegram node."""

from unittest.mock import AsyncMock, patch
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


def test_telegram_node_send_message(telegram_node):
    mock_result = AsyncMock()
    mock_result.message_id = 42

    with patch("telegram.Bot") as mock_bot:
        mock_bot.return_value.send_message = AsyncMock(return_value=mock_result)
        result = telegram_node.run(State())

        assert result == {"message_id": 42, "status": "sent"}
        mock_bot.assert_called_once_with(token="test_token")
        mock_bot.return_value.send_message.assert_called_once_with(
            chat_id="123456", text="Test message"
        )
