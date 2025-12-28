"""Tests for WeCom nodes."""

from __future__ import annotations
import base64
import hashlib
import struct
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from Crypto.Cipher import AES
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.wecom import (
    WeComAccessTokenNode,
    WeComEventsParserNode,
    WeComSendMessageNode,
)


# Test fixtures and helpers


def _create_aes_key() -> tuple[str, bytes]:
    """Create a valid AES key for testing.

    Returns:
        Tuple of (encoding_aes_key, raw_aes_key).
    """
    # WeCom uses 43-char base64 key that decodes to 32 bytes (256-bit AES)
    raw_key = b"0123456789abcdef0123456789abcdef"  # 32 bytes
    encoding_aes_key = base64.b64encode(raw_key).decode().rstrip("=")
    return encoding_aes_key, raw_key


def _encrypt_message(message: str, aes_key: bytes, corp_id: str) -> str:
    """Encrypt a message using WeCom's encryption format.

    Args:
        message: The message to encrypt.
        aes_key: The raw AES key (32 bytes).
        corp_id: The corp ID to append.

    Returns:
        Base64-encoded encrypted message.
    """
    # Format: random(16) + msg_len(4, big-endian) + msg + receive_id
    random_bytes = b"0123456789abcdef"  # 16 bytes
    msg_bytes = message.encode("utf-8")
    msg_len = struct.pack(">I", len(msg_bytes))
    content = random_bytes + msg_len + msg_bytes + corp_id.encode("utf-8")

    # PKCS7 padding to 32-byte blocks
    block_size = 32
    pad_len = block_size - (len(content) % block_size)
    content += bytes([pad_len] * pad_len)

    cipher = AES.new(aes_key, AES.MODE_CBC, aes_key[:16])
    encrypted = cipher.encrypt(content)
    return base64.b64encode(encrypted).decode()


def _sign_wecom(token: str, timestamp: str, nonce: str, data: str) -> str:
    """Create WeCom signature.

    Args:
        token: WeCom token.
        timestamp: Unix timestamp as string.
        nonce: Random nonce.
        data: echostr or encrypted message.

    Returns:
        SHA1 signature.
    """
    items = sorted([token, timestamp, nonce, data])
    return hashlib.sha1("".join(items).encode()).hexdigest()


def _build_state(
    query_params: dict[str, str] | None = None,
    body: str | dict[str, Any] | None = None,
) -> State:
    """Build a State object for testing."""
    inputs: dict[str, Any] = {}
    if query_params:
        inputs["query_params"] = query_params
    if body is not None:
        inputs["body"] = body
    return State(messages=[], inputs=inputs, results={})


# WeComEventsParserNode tests


class TestWeComEventsParserNode:
    """Tests for WeComEventsParserNode."""

    def test_verify_signature_success(self) -> None:
        """Test successful signature verification."""
        token = "test_token"
        timestamp = "1234567890"
        nonce = "abc123"
        data = "encrypted_data"
        signature = _sign_wecom(token, timestamp, nonce, data)

        node = WeComEventsParserNode(
            name="wecom_parser",
            token=token,
            encoding_aes_key="dummy",
            corp_id="corp123",
        )
        # Should not raise
        node.verify_signature(token, timestamp, nonce, data, signature)

    def test_verify_signature_failure(self) -> None:
        """Test signature verification failure."""
        token = "test_token"
        timestamp = "1234567890"
        nonce = "abc123"
        data = "encrypted_data"
        bad_signature = "bad_signature"

        node = WeComEventsParserNode(
            name="wecom_parser",
            token=token,
            encoding_aes_key="dummy",
            corp_id="corp123",
        )
        with pytest.raises(ValueError, match="WeCom signature verification failed"):
            node.verify_signature(token, timestamp, nonce, data, bad_signature)

    def test_decrypt_message(self) -> None:
        """Test message decryption."""
        encoding_aes_key, raw_key = _create_aes_key()
        corp_id = "corp123"
        original_message = "<xml><Content>Hello</Content></xml>"
        encrypted = _encrypt_message(original_message, raw_key, corp_id)

        node = WeComEventsParserNode(
            name="wecom_parser",
            token="token",
            encoding_aes_key=encoding_aes_key,
            corp_id=corp_id,
        )
        decrypted = node.decrypt_message(encrypted, encoding_aes_key)
        assert decrypted == original_message

    def test_parse_xml(self) -> None:
        """Test XML parsing."""
        node = WeComEventsParserNode(
            name="wecom_parser",
            token="token",
            encoding_aes_key="key",
            corp_id="corp123",
        )
        xml_str = "<xml><ToUserName>user1</ToUserName><Content>Hello</Content></xml>"
        result = node.parse_xml(xml_str)
        assert result == {"ToUserName": "user1", "Content": "Hello"}

    def test_is_direct_message_true(self) -> None:
        """Test direct message detection returns True for valid DM."""
        node = WeComEventsParserNode(
            name="wecom_parser",
            token="token",
            encoding_aes_key="key",
            corp_id="corp123",
        )
        assert node.is_direct_message("text", "", "Hello") is True

    def test_is_direct_message_false_with_chat_id(self) -> None:
        """Test direct message detection returns False for group messages."""
        node = WeComEventsParserNode(
            name="wecom_parser",
            token="token",
            encoding_aes_key="key",
            corp_id="corp123",
        )
        assert node.is_direct_message("text", "chat123", "Hello") is False

    def test_is_direct_message_false_for_non_text(self) -> None:
        """Test direct message detection returns False for non-text messages."""
        node = WeComEventsParserNode(
            name="wecom_parser",
            token="token",
            encoding_aes_key="key",
            corp_id="corp123",
        )
        assert node.is_direct_message("image", "", "Hello") is False

    def test_is_direct_message_false_for_empty_content(self) -> None:
        """Test direct message detection returns False for empty content."""
        node = WeComEventsParserNode(
            name="wecom_parser",
            token="token",
            encoding_aes_key="key",
            corp_id="corp123",
        )
        assert node.is_direct_message("text", "", "   ") is False

    @pytest.mark.asyncio
    async def test_url_verification(self) -> None:
        """Test URL verification flow."""
        encoding_aes_key, raw_key = _create_aes_key()
        token = "test_token"
        timestamp = str(int(time.time()))
        nonce = "nonce123"
        corp_id = "corp123"

        # Encrypt the echostr
        echostr_plain = "echo_string_12345"
        echostr_encrypted = _encrypt_message(echostr_plain, raw_key, corp_id)
        signature = _sign_wecom(token, timestamp, nonce, echostr_encrypted)

        node = WeComEventsParserNode(
            name="wecom_parser",
            token=token,
            encoding_aes_key=encoding_aes_key,
            corp_id=corp_id,
        )

        state = _build_state(
            query_params={
                "msg_signature": signature,
                "timestamp": timestamp,
                "nonce": nonce,
                "echostr": echostr_encrypted,
            }
        )

        result = await node.run(state, RunnableConfig())

        assert result["is_verification"] is True
        assert result["should_process"] is False
        assert result["immediate_response"]["content"] == echostr_plain
        assert result["immediate_response"]["status_code"] == 200

    @pytest.mark.asyncio
    async def test_encrypted_message_parsing(self) -> None:
        """Test parsing encrypted message body."""
        encoding_aes_key, raw_key = _create_aes_key()
        token = "test_token"
        timestamp = str(int(time.time()))
        nonce = "nonce123"
        corp_id = "corp123"

        # Create encrypted message content
        inner_xml = (
            "<xml>"
            "<ToUserName>app123</ToUserName>"
            "<FromUserName>user456</FromUserName>"
            "<MsgType>text</MsgType>"
            "<Content>Hello World</Content>"
            "</xml>"
        )
        encrypted = _encrypt_message(inner_xml, raw_key, corp_id)
        signature = _sign_wecom(token, timestamp, nonce, encrypted)

        # Outer XML envelope
        body_xml = f"<xml><Encrypt>{encrypted}</Encrypt></xml>"

        node = WeComEventsParserNode(
            name="wecom_parser",
            token=token,
            encoding_aes_key=encoding_aes_key,
            corp_id=corp_id,
        )

        state = _build_state(
            query_params={
                "msg_signature": signature,
                "timestamp": timestamp,
                "nonce": nonce,
            },
            body={"raw": body_xml},
        )

        result = await node.run(state, RunnableConfig())

        assert result["is_verification"] is False
        assert result["event_type"] == "text"
        assert result["content"] == "Hello World"
        assert result["user"] == "user456"
        assert result["should_process"] is True

    @pytest.mark.asyncio
    async def test_group_message_ignored(self) -> None:
        """Test that group messages are ignored."""
        encoding_aes_key, raw_key = _create_aes_key()
        token = "test_token"
        timestamp = str(int(time.time()))
        nonce = "nonce123"
        corp_id = "corp123"

        inner_xml = (
            "<xml>"
            "<ToUserName>app123</ToUserName>"
            "<FromUserName>user456</FromUserName>"
            "<MsgType>text</MsgType>"
            "<Content>Hello</Content>"
            "<ChatId>group789</ChatId>"
            "</xml>"
        )
        encrypted = _encrypt_message(inner_xml, raw_key, corp_id)
        signature = _sign_wecom(token, timestamp, nonce, encrypted)
        body_xml = f"<xml><Encrypt>{encrypted}</Encrypt></xml>"

        node = WeComEventsParserNode(
            name="wecom_parser",
            token=token,
            encoding_aes_key=encoding_aes_key,
            corp_id=corp_id,
        )

        state = _build_state(
            query_params={
                "msg_signature": signature,
                "timestamp": timestamp,
                "nonce": nonce,
            },
            body={"raw": body_xml},
        )

        result = await node.run(state, RunnableConfig())

        assert result["should_process"] is False
        assert result["chat_id"] == "group789"

    @pytest.mark.asyncio
    async def test_no_encrypt_element(self) -> None:
        """Test handling of message without Encrypt element."""
        node = WeComEventsParserNode(
            name="wecom_parser",
            token="token",
            encoding_aes_key="key",
            corp_id="corp123",
        )

        state = _build_state(
            query_params={
                "msg_signature": "",
                "timestamp": "",
                "nonce": "",
            },
            body={"raw": "<xml><Empty/></xml>"},
        )

        result = await node.run(state, RunnableConfig())

        assert result["is_verification"] is False
        assert result["event_type"] is None
        assert result["should_process"] is False

    @pytest.mark.asyncio
    async def test_timestamp_tolerance_allows_valid_timestamp(self) -> None:
        """Test that valid timestamps pass tolerance check."""
        encoding_aes_key, raw_key = _create_aes_key()
        token = "test_token"
        current_timestamp = str(int(time.time()))
        nonce = "nonce123"
        corp_id = "corp123"

        inner_xml = "<xml><MsgType>text</MsgType><Content>Hi</Content></xml>"
        encrypted = _encrypt_message(inner_xml, raw_key, corp_id)
        signature = _sign_wecom(token, current_timestamp, nonce, encrypted)
        body_xml = f"<xml><Encrypt>{encrypted}</Encrypt></xml>"

        node = WeComEventsParserNode(
            name="wecom_parser",
            token=token,
            encoding_aes_key=encoding_aes_key,
            corp_id=corp_id,
            timestamp_tolerance_seconds=300,  # 5 minutes
        )

        state = _build_state(
            query_params={
                "msg_signature": signature,
                "timestamp": current_timestamp,
                "nonce": nonce,
            },
            body={"raw": body_xml},
        )

        # Should not raise - valid timestamp
        result = await node.run(state, RunnableConfig())
        assert result["event_type"] == "text"

    @pytest.mark.asyncio
    async def test_immediate_response_check(self) -> None:
        """Test immediate response check mode."""
        node = WeComEventsParserNode(
            name="wecom_parser",
            token="token",
            encoding_aes_key="key",
            corp_id="corp123",
        )

        state = _build_state(
            query_params={},
            body={"raw": "<xml><Empty/></xml>"},
        )

        config = RunnableConfig(configurable={"thread_id": "immediate-response-check"})
        result = await node.run(state, config)

        assert result["immediate_response"] == {
            "content": "success",
            "content_type": "text/plain",
            "status_code": 200,
        }


# WeComAccessTokenNode tests


class TestWeComAccessTokenNode:
    """Tests for WeComAccessTokenNode."""

    @pytest.mark.asyncio
    async def test_fetch_access_token_success(self) -> None:
        """Test successful access token fetch."""
        node = WeComAccessTokenNode(
            name="get_token",
            corp_id="corp123",
            corp_secret="secret456",
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "errcode": 0,
            "errmsg": "ok",
            "access_token": "test_access_token",
            "expires_in": 7200,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        with patch("orcheo.nodes.wecom.httpx.AsyncClient", return_value=mock_client):
            result = await node.run({}, RunnableConfig())

        assert result["access_token"] == "test_access_token"
        assert result["expires_in"] == 7200

        mock_client.get.assert_called_once_with(
            "https://qyapi.weixin.qq.com/cgi-bin/gettoken",
            params={"corpid": "corp123", "corpsecret": "secret456"},
        )

    @pytest.mark.asyncio
    async def test_fetch_access_token_error(self) -> None:
        """Test access token fetch with API error."""
        node = WeComAccessTokenNode(
            name="get_token",
            corp_id="corp123",
            corp_secret="bad_secret",
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "errcode": 40001,
            "errmsg": "invalid credential",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        with patch("orcheo.nodes.wecom.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(
                ValueError, match="WeCom token error: invalid credential"
            ):
                await node.run({}, RunnableConfig())


# WeComSendMessageNode tests


class TestWeComSendMessageNode:
    """Tests for WeComSendMessageNode."""

    @pytest.mark.asyncio
    async def test_send_text_message_to_user(self) -> None:
        """Test sending text message to user."""
        node = WeComSendMessageNode(
            name="send_msg",
            agent_id=1000001,
            to_user="user123",
            message="Hello, user!",
        )

        state = State(
            messages=[],
            inputs={},
            results={"get_access_token": {"access_token": "test_token"}},
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        with patch("orcheo.nodes.wecom.httpx.AsyncClient", return_value=mock_client):
            result = await node.run(state, RunnableConfig())

        assert result["is_error"] is False
        assert result["errcode"] == 0

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["json"]["touser"] == "user123"
        assert call_kwargs[1]["json"]["text"]["content"] == "Hello, user!"

    @pytest.mark.asyncio
    async def test_send_markdown_message(self) -> None:
        """Test sending markdown message."""
        node = WeComSendMessageNode(
            name="send_msg",
            agent_id="1000001",  # String agent_id
            to_user="user123",
            message="**Bold** text",
            msg_type="markdown",
        )

        state = State(
            messages=[],
            inputs={},
            results={"get_access_token": {"access_token": "test_token"}},
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        with patch("orcheo.nodes.wecom.httpx.AsyncClient", return_value=mock_client):
            result = await node.run(state, RunnableConfig())

        assert result["is_error"] is False
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["json"]["markdown"]["content"] == "**Bold** text"
        assert call_kwargs[1]["json"]["msgtype"] == "markdown"

    @pytest.mark.asyncio
    async def test_send_message_to_chat(self) -> None:
        """Test sending message to group chat."""
        node = WeComSendMessageNode(
            name="send_msg",
            agent_id=1000001,
            chat_id="chat789",
            message="Hello, group!",
        )

        state = State(
            messages=[],
            inputs={},
            results={"get_access_token": {"access_token": "test_token"}},
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        with patch("orcheo.nodes.wecom.httpx.AsyncClient", return_value=mock_client):
            result = await node.run(state, RunnableConfig())

        assert result["is_error"] is False
        call_kwargs = mock_client.post.call_args
        assert "chatid" in call_kwargs[1]["json"]
        assert call_kwargs[0][0] == "https://qyapi.weixin.qq.com/cgi-bin/appchat/send"

    @pytest.mark.asyncio
    async def test_send_message_no_access_token(self) -> None:
        """Test sending message without access token."""
        node = WeComSendMessageNode(
            name="send_msg",
            agent_id=1000001,
            to_user="user123",
            message="Hello!",
        )

        state = State(messages=[], inputs={}, results={})

        result = await node.run(state, RunnableConfig())

        assert result["is_error"] is True
        assert result["error"] == "No access token available"

    @pytest.mark.asyncio
    async def test_send_message_no_recipient(self) -> None:
        """Test sending message without recipient."""
        node = WeComSendMessageNode(
            name="send_msg",
            agent_id=1000001,
            message="Hello!",
        )

        state = State(
            messages=[],
            inputs={},
            results={"get_access_token": {"access_token": "test_token"}},
        )

        result = await node.run(state, RunnableConfig())

        assert result["is_error"] is True
        assert "No WeCom chat_id or to_user provided" in result["error"]

    @pytest.mark.asyncio
    async def test_send_message_uses_parser_target_user(self) -> None:
        """Test that send message uses target_user from parser result."""
        node = WeComSendMessageNode(
            name="send_msg",
            agent_id=1000001,
            message="Reply!",
        )

        state = State(
            messages=[],
            inputs={},
            results={
                "get_access_token": {"access_token": "test_token"},
                "wecom_events_parser": {"target_user": "parsed_user"},
            },
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        with patch("orcheo.nodes.wecom.httpx.AsyncClient", return_value=mock_client):
            result = await node.run(state, RunnableConfig())

        assert result["is_error"] is False
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["json"]["touser"] == "parsed_user"

    @pytest.mark.asyncio
    async def test_send_message_api_error(self) -> None:
        """Test handling of API error response."""
        node = WeComSendMessageNode(
            name="send_msg",
            agent_id=1000001,
            to_user="user123",
            message="Hello!",
        )

        state = State(
            messages=[],
            inputs={},
            results={"get_access_token": {"access_token": "test_token"}},
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "errcode": 60011,
            "errmsg": "no privilege to access",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        with patch("orcheo.nodes.wecom.httpx.AsyncClient", return_value=mock_client):
            result = await node.run(state, RunnableConfig())

        assert result["is_error"] is True
        assert result["errcode"] == 60011
        assert result["errmsg"] == "no privilege to access"
