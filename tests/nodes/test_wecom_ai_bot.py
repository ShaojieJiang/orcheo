"""Tests for WeCom AI bot nodes."""

from __future__ import annotations
import base64
import hashlib
import json
import struct
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from Crypto.Cipher import AES
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.wecom import (
    WeComAIBotEventsParserNode,
    WeComAIBotPassiveReplyNode,
    WeComAIBotResponseNode,
)


def _create_aes_key() -> tuple[str, bytes]:
    """Create a valid AES key for testing."""
    raw_key = b"0123456789abcdef0123456789abcdef"
    encoding_aes_key = base64.b64encode(raw_key).decode().rstrip("=")
    return encoding_aes_key, raw_key


def _encrypt_message(message: str, aes_key: bytes, receive_id: str) -> str:
    """Encrypt a message using WeCom's encryption format."""
    random_bytes = b"0123456789abcdef"
    msg_bytes = message.encode("utf-8")
    msg_len = struct.pack(">I", len(msg_bytes))
    content = random_bytes + msg_len + msg_bytes + receive_id.encode("utf-8")

    block_size = 32
    pad_len = block_size - (len(content) % block_size)
    content += bytes([pad_len] * pad_len)

    cipher = AES.new(aes_key, AES.MODE_CBC, aes_key[:16])
    encrypted = cipher.encrypt(content)
    return base64.b64encode(encrypted).decode()


def _sign_wecom(token: str, timestamp: str, nonce: str, data: str) -> str:
    """Create WeCom signature."""
    items = sorted([token, timestamp, nonce, data])
    return hashlib.sha1("".join(items).encode()).hexdigest()


def _build_state(
    query_params: dict[str, str] | None = None,
    body: str | dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> State:
    """Build a State object for testing."""
    inputs: dict[str, Any] = {}
    if query_params:
        inputs["query_params"] = query_params
    if body is not None:
        inputs["body"] = body
    return State(messages=[], inputs=inputs, results={}, config=config or {})


class TestWeComAIBotEventsParserNode:
    """Tests for WeComAIBotEventsParserNode."""

    @pytest.mark.asyncio
    async def test_url_verification(self) -> None:
        """Test AI bot URL verification flow."""
        encoding_aes_key, raw_key = _create_aes_key()
        token = "test_token"
        timestamp = str(int(time.time()))
        nonce = "nonce123"

        echostr_plain = "echo_string_123"
        echostr_encrypted = _encrypt_message(echostr_plain, raw_key, "")
        signature = _sign_wecom(token, timestamp, nonce, echostr_encrypted)

        node = WeComAIBotEventsParserNode(
            name="wecom_ai_bot_parser",
            token=token,
            encoding_aes_key=encoding_aes_key,
            receive_id="",
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

    @pytest.mark.asyncio
    async def test_encrypted_message_parsing(self) -> None:
        """Test parsing encrypted AI bot JSON payload."""
        encoding_aes_key, raw_key = _create_aes_key()
        token = "test_token"
        timestamp = str(int(time.time()))
        nonce = "nonce123"

        msg_payload = {
            "msgid": "msg123",
            "aibotid": "bot123",
            "chattype": "single",
            "response_url": "https://example.com/response",
            "msgtype": "text",
            "from": {"userid": "user456"},
            "text": {"content": "Hello AI"},
        }
        encrypted = _encrypt_message(json.dumps(msg_payload), raw_key, "")
        signature = _sign_wecom(token, timestamp, nonce, encrypted)

        node = WeComAIBotEventsParserNode(
            name="wecom_ai_bot_parser",
            token=token,
            encoding_aes_key=encoding_aes_key,
            receive_id="",
        )

        state = _build_state(
            query_params={
                "msg_signature": signature,
                "timestamp": timestamp,
                "nonce": nonce,
            },
            body={"encrypt": encrypted},
        )

        result = await node.run(state, RunnableConfig())

        assert result["msg_type"] == "text"
        assert result["chat_type"] == "single"
        assert result["response_url"] == "https://example.com/response"
        assert result["user"] == "user456"
        assert result["content"] == "Hello AI"
        assert result["should_process"] is True
        assert result["immediate_response"] is None

    @pytest.mark.asyncio
    async def test_encrypted_message_immediate_response_check_active_reply(
        self,
    ) -> None:
        """Test immediate-response-check with active reply returns success for async."""
        encoding_aes_key, raw_key = _create_aes_key()
        token = "test_token"
        timestamp = str(int(time.time()))
        nonce = "nonce123"

        msg_payload = {
            "msgid": "msg123",
            "aibotid": "bot123",
            "chattype": "single",
            "response_url": "https://example.com/response",
            "msgtype": "text",
            "from": {"userid": "user456"},
            "text": {"content": "Hello AI"},
        }
        encrypted = _encrypt_message(json.dumps(msg_payload), raw_key, "")
        signature = _sign_wecom(token, timestamp, nonce, encrypted)

        node = WeComAIBotEventsParserNode(
            name="wecom_ai_bot_parser",
            token=token,
            encoding_aes_key=encoding_aes_key,
            receive_id="",
        )

        # Active reply mode: use_passive_reply is False
        state = _build_state(
            query_params={
                "msg_signature": signature,
                "timestamp": timestamp,
                "nonce": nonce,
            },
            body={"encrypt": encrypted},
            config={"configurable": {"use_passive_reply": False}},
        )

        # Simulate immediate-response-check execution
        config = RunnableConfig(
            configurable={"thread_id": "immediate-response-check-abc123"}
        )
        result = await node.run(state, config)

        # Active reply mode: parser returns success immediately, queues async run
        assert result["should_process"] is True
        assert result["immediate_response"] is not None
        assert result["immediate_response"]["content"] == "success"
        assert result["immediate_response"]["status_code"] == 200

    @pytest.mark.asyncio
    async def test_encrypted_message_immediate_response_check_passive_reply(
        self,
    ) -> None:
        """Test immediate-response-check with passive reply does not short-circuit."""
        encoding_aes_key, raw_key = _create_aes_key()
        token = "test_token"
        timestamp = str(int(time.time()))
        nonce = "nonce123"

        msg_payload = {
            "msgid": "msg123",
            "aibotid": "bot123",
            "chattype": "single",
            "response_url": "https://example.com/response",
            "msgtype": "text",
            "from": {"userid": "user456"},
            "text": {"content": "Hello AI"},
        }
        encrypted = _encrypt_message(json.dumps(msg_payload), raw_key, "")
        signature = _sign_wecom(token, timestamp, nonce, encrypted)

        node = WeComAIBotEventsParserNode(
            name="wecom_ai_bot_parser",
            token=token,
            encoding_aes_key=encoding_aes_key,
            receive_id="",
        )

        # Passive reply mode: use_passive_reply is True
        state = _build_state(
            query_params={
                "msg_signature": signature,
                "timestamp": timestamp,
                "nonce": nonce,
            },
            body={"encrypt": encrypted},
            config={"configurable": {"use_passive_reply": True}},
        )

        # Simulate immediate-response-check execution
        config = RunnableConfig(
            configurable={"thread_id": "immediate-response-check-abc123"}
        )
        result = await node.run(state, config)

        # Passive reply mode: parser doesn't set immediate_response,
        # lets workflow continue to passive_reply node
        assert result["should_process"] is True
        assert result["immediate_response"] is None
        assert result["msg_type"] == "text"
        assert result["content"] == "Hello AI"

    @pytest.mark.asyncio
    async def test_missing_encrypt_returns_invalid(self) -> None:
        """Test missing encrypt field returns invalid payload response."""
        node = WeComAIBotEventsParserNode(
            name="wecom_ai_bot_parser",
            token="token",
            encoding_aes_key="key",
            receive_id="",
        )

        state = _build_state(
            query_params={
                "msg_signature": "",
                "timestamp": "",
                "nonce": "",
            },
            body={"missing": "encrypt"},
        )

        result = await node.run(state, RunnableConfig())

        assert result["is_verification"] is False
        assert result["should_process"] is False
        assert result["immediate_response"] is None


class TestWeComAIBotPassiveReplyNode:
    """Tests for WeComAIBotPassiveReplyNode."""

    @pytest.mark.asyncio
    async def test_passive_reply_encrypts_payload(self) -> None:
        """Test passive reply encryption and signature."""
        encoding_aes_key, _ = _create_aes_key()
        token = "test_token"

        node = WeComAIBotPassiveReplyNode(
            name="passive_reply",
            token=token,
            encoding_aes_key=encoding_aes_key,
            msg_type="markdown",
            content="Hello AI",
            receive_id="",
        )

        result = await node.run(
            State(messages=[], inputs={}, results={}), RunnableConfig()
        )

        assert result["is_error"] is False
        response_body = json.loads(result["immediate_response"]["content"])
        signature = _sign_wecom(
            token,
            str(response_body["timestamp"]),
            response_body["nonce"],
            response_body["encrypt"],
        )
        assert response_body["msgsignature"] == signature

        parser = WeComAIBotEventsParserNode(
            name="parser",
            token=token,
            encoding_aes_key=encoding_aes_key,
            receive_id="",
        )
        decrypted = parser.decrypt_message(
            response_body["encrypt"],
            encoding_aes_key,
            None,
        )
        payload = json.loads(decrypted)
        assert payload["msgtype"] == "markdown"
        assert payload["markdown"]["content"] == "Hello AI"


class TestWeComAIBotResponseNode:
    """Tests for WeComAIBotResponseNode."""

    @pytest.mark.asyncio
    async def test_response_url_delivery_success(self) -> None:
        """Test active reply delivery to response_url."""
        node = WeComAIBotResponseNode(
            name="aibot_response",
            response_url="https://example.com/response",
            msg_type="markdown",
            content="Thanks!",
        )

        state = State(messages=[], inputs={}, results={})

        mock_response = MagicMock()
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_response.raise_for_status = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        with patch("orcheo.nodes.wecom.httpx.AsyncClient", return_value=mock_client):
            result = await node.run(state, RunnableConfig())

        assert result["is_error"] is False
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == "https://example.com/response"
        assert call_kwargs[1]["json"]["markdown"]["content"] == "Thanks!"
