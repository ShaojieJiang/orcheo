"""Tests for Telegram node."""

from unittest.mock import AsyncMock, patch
import pytest
from telegram import Message
from orcheo.graph.state import State
from orcheo.nodes.telegram import MessageTelegram, escape_markdown


def test_escape_markdown():
    """Test markdown escaping function."""
    text = "Hello! This is a *bold* _italic_ [text](http://example.com)"
    escaped = escape_markdown(text)
    assert (
        escaped
        == "Hello\\! This is a \\*bold\\* \\_italic\\_ \\[text\\]\\(http://example\\.com\\)"
    )


@pytest.fixture
def telegram_node():
    return MessageTelegram(
        name="telegram_node",
        token="test_token",
        chat_id="123456",
        message="Test message!",
    )


@pytest.mark.asyncio
async def test_telegram_node_send_message(telegram_node):
    mock_message = AsyncMock(spec=Message)
    mock_message.message_id = 42

    mock_bot = AsyncMock()
    mock_bot.send_message = AsyncMock(return_value=mock_message)

    with patch("orcheo.nodes.telegram.Bot", return_value=mock_bot):
        result = await telegram_node.run(State(), None)

        assert result == {"message_id": 42, "status": "sent"}
        mock_bot.send_message.assert_called_once_with(
            chat_id="123456", text="Test message!", parse_mode=None
        )


@pytest.mark.asyncio
async def test_telegram_node_error_handling(telegram_node):
    mock_bot = AsyncMock()
    mock_bot.send_message = AsyncMock(
        side_effect=Exception("Bad Request: message text is empty")
    )

    with patch("orcheo.nodes.telegram.Bot", return_value=mock_bot):
        with pytest.raises(
            ValueError, match="Telegram API error: Bad Request: message text is empty"
        ):
            await telegram_node.run(State(), None)


@pytest.mark.asyncio
async def test_telegram_node_send_message_with_parse_mode():
    telegram_node = MessageTelegram(
        name="telegram_node",
        token="test_token",
        chat_id="123456",
        message="Test message!",
        parse_mode="MarkdownV2",
    )
    mock_message = AsyncMock(spec=Message)
    mock_message.message_id = 42

    mock_bot = AsyncMock()
    mock_bot.send_message = AsyncMock(return_value=mock_message)

    with patch("orcheo.nodes.telegram.Bot", return_value=mock_bot):
        result = await telegram_node.run(State(), None)

        assert result == {"message_id": 42, "status": "sent"}
        mock_bot.send_message.assert_called_once_with(
            chat_id="123456",
            text="Test message!",
            parse_mode="MarkdownV2",
        )


@pytest.mark.asyncio
async def test_telegram_node_tool_run(telegram_node):
    mock_message = AsyncMock(spec=Message)
    mock_message.message_id = 42

    mock_bot = AsyncMock()
    mock_bot.send_message = AsyncMock(return_value=mock_message)

    with patch("orcheo.nodes.telegram.Bot", return_value=mock_bot):
        with patch("asyncio.run") as mock_asyncio_run:
            # Mock asyncio.run to directly call the async function
            async def mock_run(coro):
                return await coro

            mock_asyncio_run.side_effect = mock_run

            result = await telegram_node.tool_arun("123456", "Test message!")
            assert result == {"message_id": 42, "status": "sent"}
            mock_bot.send_message.assert_called_once_with(
                chat_id="123456", text="Test message!", parse_mode=None
            )
