"""WeCom integration nodes for Orcheo.

This module provides nodes for integrating with WeCom (企业微信) APIs:
- WeComEventsParserNode: Validates signatures and parses callback payloads
- WeComAccessTokenNode: Fetches WeCom access tokens
- WeComSendMessageNode: Sends messages to WeCom chats
"""

import base64
import hashlib
import hmac
import struct
import time
from typing import Any
from xml.etree import ElementTree
import httpx
from Crypto.Cipher import AES
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="WeComEventsParserNode",
        description="Validate WeCom signatures and parse callback payloads",
        category="wecom",
    )
)
class WeComEventsParserNode(TaskNode):
    """Validate WeCom signatures and parse callback payloads.

    Handles:
    - URL verification (GET with echostr)
    - Message decryption for encrypted callbacks
    - Signature validation using Token
    - Filtering for direct messages only
    """

    token: str = "[[wecom_token]]"
    """WeCom callback token for signature validation (from Orcheo vault)."""
    encoding_aes_key: str = "[[wecom_encoding_aes_key]]"
    """WeCom AES key for payload decryption (from Orcheo vault)."""
    corp_id: str = Field(description="WeCom corp ID for decryption validation")
    timestamp_tolerance_seconds: int = Field(
        default=300,
        description="Maximum age for WeCom signature timestamps",
    )

    def verify_signature(
        self,
        token: str,
        timestamp: str,
        nonce: str,
        echostr_or_encrypt: str,
        signature: str,
    ) -> None:
        """Verify WeCom message signature."""
        items = sorted([token, timestamp, nonce, echostr_or_encrypt])
        sha1 = hashlib.sha1("".join(items).encode()).hexdigest()
        if not hmac.compare_digest(sha1, signature):
            msg = "WeCom signature verification failed"
            raise ValueError(msg)

    def decrypt_message(self, encrypt: str, encoding_aes_key: str) -> str:
        """Decrypt WeCom encrypted message."""
        aes_key = base64.b64decode(encoding_aes_key + "=")
        cipher = AES.new(aes_key, AES.MODE_CBC, aes_key[:16])
        decrypted = cipher.decrypt(base64.b64decode(encrypt))

        # Remove PKCS7 padding
        pad_len = decrypted[-1]
        content = decrypted[:-pad_len]

        # Parse format: random(16) + msg_len(4) + msg + receive_id
        msg_len = struct.unpack(">I", content[16:20])[0]
        msg = content[20 : 20 + msg_len].decode("utf-8")
        return msg

    def parse_xml(self, xml_str: str) -> dict[str, str]:
        """Parse WeCom XML payload."""
        root = ElementTree.fromstring(xml_str)
        return {child.tag: (child.text or "") for child in root}

    def extract_inputs(self, state: State) -> dict[str, Any]:
        """Extract inputs from state."""
        state_dict = dict(state)
        raw_inputs = state_dict.get("inputs")
        if isinstance(raw_inputs, dict):
            return dict(raw_inputs)
        return state_dict

    def is_immediate_response_check(self, config: RunnableConfig) -> bool:
        """Check if this is a synchronous immediate-response check execution."""
        configurable = config.get("configurable", {})
        thread_id = configurable.get("thread_id", "")
        return thread_id == "immediate-response-check"

    def success_response(self) -> dict[str, Any]:
        """Return a success immediate_response dict."""
        return {
            "content": "success",
            "content_type": "text/plain",
            "status_code": 200,
        }

    def add_immediate_response(
        self, result: dict[str, Any], is_sync_check: bool
    ) -> dict[str, Any]:
        """Add immediate_response to result if this is a sync check."""
        if is_sync_check:
            result["immediate_response"] = self.success_response()
        else:
            result.setdefault("immediate_response", None)
        return result

    def is_direct_message(self, msg_type: str, chat_id: str, content: str) -> bool:
        """Return whether the message is a direct message to the app."""
        if chat_id:
            return False
        if msg_type != "text":
            return False
        return bool(content.strip())

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Parse the WeCom callback payload and validate signatures."""
        is_sync_check = self.is_immediate_response_check(config)
        inputs = self.extract_inputs(state)
        query_params = inputs.get("query_params", {})

        msg_signature = query_params.get("msg_signature", "")
        timestamp = query_params.get("timestamp", "")
        nonce = query_params.get("nonce", "")
        echostr = query_params.get("echostr")

        # URL verification request (GET with echostr)
        # Always return immediate_response for verification
        if echostr:
            self.verify_signature(self.token, timestamp, nonce, echostr, msg_signature)
            decrypted_echostr = self.decrypt_message(echostr, self.encoding_aes_key)
            return {
                "is_verification": True,
                "should_process": False,
                "immediate_response": {
                    "content": decrypted_echostr,
                    "content_type": "text/plain",
                    "status_code": 200,
                },
            }

        # Parse encrypted message body
        body = inputs.get("body", {})
        if isinstance(body, dict) and "raw" in body:
            body_str = body["raw"]
        elif isinstance(body, str):
            body_str = body
        else:
            body_str = str(body)

        xml_data = self.parse_xml(body_str)
        encrypt = xml_data.get("Encrypt", "")

        if not encrypt:
            return self.add_immediate_response(
                {
                    "is_verification": False,
                    "event_type": None,
                    "should_process": False,
                },
                is_sync_check,
            )

        # Verify signature
        self.verify_signature(self.token, timestamp, nonce, encrypt, msg_signature)

        # Check timestamp tolerance
        if self.timestamp_tolerance_seconds:
            now = int(time.time())
            try:
                ts = int(timestamp)
                if abs(now - ts) > self.timestamp_tolerance_seconds:
                    msg = "WeCom request timestamp outside tolerance window"
                    raise ValueError(msg)
            except ValueError:
                pass

        # Decrypt message
        decrypted_xml = self.decrypt_message(encrypt, self.encoding_aes_key)
        msg_data = self.parse_xml(decrypted_xml)

        msg_type = msg_data.get("MsgType", "").strip().lower()
        chat_id = msg_data.get("ChatId", "")
        content = msg_data.get("Content", "")

        # Ignore group chat messages; only respond to direct messages.
        if chat_id:
            return self.add_immediate_response(
                {
                    "is_verification": False,
                    "event_type": msg_type,
                    "chat_id": chat_id,
                    "should_process": False,
                },
                is_sync_check,
            )

        # Direct message detection (no ChatId).
        is_direct_message = self.is_direct_message(msg_type, chat_id, content)

        # Sync check: return immediate_response to ack WeCom quickly.
        # Async run: no immediate_response, workflow continues to send_message.
        return self.add_immediate_response(
            {
                "is_verification": False,
                "event_type": msg_type,
                "chat_id": chat_id,
                "user": msg_data.get("FromUserName", ""),
                "content": content,
                "target_user": msg_data.get("FromUserName", ""),
                "should_process": is_direct_message,
            },
            is_sync_check,
        )


@registry.register(
    NodeMetadata(
        name="WeComAccessTokenNode",
        description="Fetch and cache WeCom access token",
        category="wecom",
    )
)
class WeComAccessTokenNode(TaskNode):
    """Fetch and cache WeCom access token."""

    corp_id: str = Field(description="WeCom corp ID")
    corp_secret: str = "[[wecom_corp_secret]]"
    """WeCom app secret (from Orcheo vault)."""

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Fetch access token from WeCom API."""
        url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        params = {"corpid": self.corp_id, "corpsecret": self.corp_secret}

        client = httpx.AsyncClient(timeout=10.0)
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        finally:
            await client.aclose()

        if data.get("errcode", 0) != 0:
            msg = f"WeCom token error: {data.get('errmsg', 'Unknown error')}"
            raise ValueError(msg)

        return {
            "access_token": data.get("access_token"),
            "expires_in": data.get("expires_in"),
        }


@registry.register(
    NodeMetadata(
        name="WeComSendMessageNode",
        description="Send messages to WeCom chat",
        category="wecom",
    )
)
class WeComSendMessageNode(TaskNode):
    """Send messages to WeCom chat."""

    agent_id: int | str = Field(description="WeCom app agent ID")
    chat_id: str | None = Field(
        default=None,
        description="WeCom chat ID for group message delivery",
    )
    to_user: str | None = Field(
        default=None,
        description="WeCom user ID for direct message delivery",
    )
    message: str = Field(description="Message content to send")
    msg_type: str = Field(default="text", description="Message type (text or markdown)")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Send message to WeCom chat."""
        # Get access token from previous node result
        results = state.get("results", {})
        token_result = results.get("get_access_token", {})
        access_token = token_result.get("access_token")

        if not access_token:
            return {"is_error": True, "error": "No access token available"}

        target_user = self.to_user
        if not target_user and isinstance(results, dict):
            parser_result = results.get("wecom_events_parser")
            if isinstance(parser_result, dict):
                target_user = parser_result.get("target_user")
        target_chat = self.chat_id
        if not target_user and not target_chat:
            return {
                "is_error": True,
                "error": "No WeCom chat_id or to_user provided",
            }

        url = (
            "https://qyapi.weixin.qq.com/cgi-bin/message/send"
            if target_user
            else "https://qyapi.weixin.qq.com/cgi-bin/appchat/send"
        )
        params = {"access_token": access_token}

        # Convert agent_id to int if string
        agent_id = self.agent_id
        if isinstance(agent_id, str):
            agent_id = int(agent_id)

        payload: dict[str, Any] = {
            "msgtype": self.msg_type,
            "agentid": agent_id,
            "safe": 0,
        }
        if target_user:
            payload["touser"] = target_user
        else:
            payload["chatid"] = target_chat

        if self.msg_type == "markdown":
            payload["markdown"] = {"content": self.message}
        else:
            payload["text"] = {"content": self.message}

        client = httpx.AsyncClient(timeout=10.0)
        try:
            response = await client.post(url, params=params, json=payload)
            response.raise_for_status()
            data = response.json()
        finally:
            await client.aclose()

        errcode = data.get("errcode", 0)
        if errcode != 0:
            return {
                "is_error": True,
                "errcode": errcode,
                "errmsg": data.get("errmsg", "Unknown error"),
            }

        return {
            "is_error": False,
            "errcode": 0,
            "errmsg": "ok",
        }


__all__ = [
    "WeComAccessTokenNode",
    "WeComEventsParserNode",
    "WeComSendMessageNode",
]
