"""WeCom integration nodes for Orcheo.

This module provides nodes for integrating with WeCom (企业微信) APIs:
- WeComEventsParserNode: Validates signatures and parses callback payloads
- WeComAccessTokenNode: Fetches WeCom access tokens
- WeComSendMessageNode: Sends messages to WeCom chats
- WeComCustomerServiceSyncNode: Syncs messages from Customer Service (微信客服)
- WeComCustomerServiceSendNode: Sends messages via Customer Service API
"""

import base64
import hashlib
import hmac
import logging
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


logger = logging.getLogger(__name__)


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
    allowlist_user_ids: list[str] | None = Field(
        default=None,
        description="Optional allowlist of WeCom user IDs",
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
            logger.warning(
                "WeCom signature verification failed",
                extra={
                    "event": "wecom_signature_validation",
                    "status": "failed",
                },
            )
            msg = "WeCom signature verification failed"
            raise ValueError(msg)

    def decrypt_message(
        self,
        encrypt: str,
        encoding_aes_key: str,
        expected_receive_id: str | None = None,
    ) -> str:
        """Decrypt WeCom encrypted message."""
        aes_key = base64.b64decode(encoding_aes_key + "=")
        cipher = AES.new(aes_key, AES.MODE_CBC, aes_key[:16])
        decrypted = cipher.decrypt(base64.b64decode(encrypt))

        # Remove PKCS7 padding
        pad_len = decrypted[-1]
        if pad_len < 1 or pad_len > 32:
            msg = "WeCom payload padding invalid"
            raise ValueError(msg)
        content = decrypted[:-pad_len]

        # Parse format: random(16) + msg_len(4) + msg + receive_id
        if len(content) < 20:
            msg = "WeCom payload too short"
            raise ValueError(msg)
        msg_len = struct.unpack(">I", content[16:20])[0]
        msg_end = 20 + msg_len
        if msg_end > len(content):
            msg = "WeCom payload length mismatch"
            raise ValueError(msg)
        msg = content[20:msg_end].decode("utf-8")
        receive_id = content[msg_end:].decode("utf-8")
        if expected_receive_id and receive_id != expected_receive_id:
            logger.warning(
                "WeCom receive_id validation failed",
                extra={
                    "event": "wecom_receive_id_validation",
                    "status": "failed",
                    "receive_id": receive_id,
                    "expected_receive_id": expected_receive_id,
                },
            )
            msg = "WeCom receive_id validation failed"
            raise ValueError(msg)
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

    def is_customer_service_event(self, msg_data: dict[str, str]) -> bool:
        """Return whether this is a Customer Service (微信客服) event.

        External WeChat users send messages through Customer Service,
        which triggers a kf_msg_or_event callback. This callback only signals
        that new messages are available; actual messages must be fetched
        via the sync_msg API.
        """
        msg_type = msg_data.get("MsgType", "").strip().lower()
        event = msg_data.get("Event", "").strip().lower()
        return msg_type == "event" and event == "kf_msg_or_event"

    def is_allowlisted_user(self, user_id: str) -> bool:
        """Return whether the user is allowed to send messages."""
        if not self.allowlist_user_ids:
            return True
        return user_id in self.allowlist_user_ids

    def validate_timestamp(self, timestamp: str) -> bool:
        """Validate that the timestamp is within the tolerance window.

        Returns True if valid, False if invalid or outside tolerance.
        """
        if not self.timestamp_tolerance_seconds:
            return True
        try:
            ts = int(timestamp)
        except ValueError:
            logger.warning(
                "WeCom request timestamp invalid",
                extra={
                    "event": "wecom_timestamp_validation",
                    "status": "failed",
                    "timestamp": timestamp,
                },
            )
            return False
        now = int(time.time())
        if abs(now - ts) > self.timestamp_tolerance_seconds:
            logger.warning(
                "WeCom request timestamp outside tolerance window",
                extra={
                    "event": "wecom_timestamp_validation",
                    "status": "failed",
                    "timestamp": timestamp,
                    "tolerance_seconds": self.timestamp_tolerance_seconds,
                },
            )
            return False
        return True

    def handle_internal_message(
        self, msg_data: dict[str, str], is_sync_check: bool
    ) -> dict[str, Any]:
        """Handle internal WeCom user message."""
        msg_type = msg_data.get("MsgType", "").strip().lower()
        chat_id = msg_data.get("ChatId", "")
        content = msg_data.get("Content", "")
        user_id = msg_data.get("FromUserName", "")

        # Ignore group chat messages; only respond to direct messages.
        if chat_id:
            logger.info(
                "WeCom group message ignored",
                extra={
                    "event": "wecom_message_filter",
                    "status": "ignored",
                    "chat_id": chat_id,
                },
            )
            return self.add_immediate_response(
                {
                    "is_verification": False,
                    "is_customer_service": False,
                    "event_type": msg_type,
                    "chat_id": chat_id,
                    "should_process": False,
                },
                is_sync_check,
            )

        # Direct message detection (no ChatId).
        is_direct_message = self.is_direct_message(msg_type, chat_id, content)
        is_allowlisted = self.is_allowlisted_user(user_id)
        if is_direct_message and not is_allowlisted:
            logger.warning(
                "WeCom user rejected by allowlist",
                extra={
                    "event": "wecom_allowlist_validation",
                    "status": "failed",
                    "user_id": user_id,
                },
            )

        # Sync check: return immediate_response to ack WeCom quickly.
        # Async run: no immediate_response, workflow continues to send_message.
        return self.add_immediate_response(
            {
                "is_verification": False,
                "is_customer_service": False,
                "event_type": msg_type,
                "chat_id": chat_id,
                "user": user_id,
                "content": content,
                "target_user": user_id,
                "should_process": is_direct_message and is_allowlisted,
            },
            is_sync_check,
        )

    def handle_customer_service_event(
        self, msg_data: dict[str, str], is_sync_check: bool
    ) -> dict[str, Any]:
        """Handle Customer Service (微信客服) event from external WeChat users."""
        open_kf_id = msg_data.get("OpenKfId", "")
        kf_token = msg_data.get("Token", "")
        logger.info(
            "WeCom Customer Service event received",
            extra={
                "event": "wecom_customer_service",
                "status": "received",
                "open_kf_id": open_kf_id,
            },
        )
        return self.add_immediate_response(
            {
                "is_verification": False,
                "is_customer_service": True,
                "event_type": "kf_msg_or_event",
                "open_kf_id": open_kf_id,
                "kf_token": kf_token,
                "should_process": bool(open_kf_id and kf_token),
            },
            is_sync_check,
        )

    def handle_url_verification(
        self, timestamp: str, nonce: str, echostr: str, msg_signature: str
    ) -> dict[str, Any]:
        """Handle URL verification request (GET with echostr)."""
        self.verify_signature(self.token, timestamp, nonce, echostr, msg_signature)
        decrypted_echostr = self.decrypt_message(
            echostr, self.encoding_aes_key, self.corp_id
        )
        return {
            "is_verification": True,
            "should_process": False,
            "immediate_response": {
                "content": decrypted_echostr,
                "content_type": "text/plain",
                "status_code": 200,
            },
        }

    def extract_body_string(self, inputs: dict[str, Any]) -> str:
        """Extract body string from inputs."""
        body = inputs.get("body", {})
        if isinstance(body, dict) and "raw" in body:
            return body["raw"]
        if isinstance(body, str):
            return body
        return str(body)

    def make_invalid_payload_response(self, is_sync_check: bool) -> dict[str, Any]:
        """Return a response for invalid/missing payload."""
        return self.add_immediate_response(
            {
                "is_verification": False,
                "event_type": None,
                "should_process": False,
            },
            is_sync_check,
        )

    def decrypt_and_parse_message(
        self, encrypt: str, timestamp: str, nonce: str, msg_signature: str
    ) -> dict[str, str]:
        """Verify signature, validate timestamp, decrypt and parse message."""
        self.verify_signature(self.token, timestamp, nonce, encrypt, msg_signature)
        decrypted_xml = self.decrypt_message(
            encrypt, self.encoding_aes_key, self.corp_id
        )
        return self.parse_xml(decrypted_xml)

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
        if echostr:
            return self.handle_url_verification(
                timestamp, nonce, echostr, msg_signature
            )

        # Parse encrypted message body
        body_str = self.extract_body_string(inputs)
        xml_data = self.parse_xml(body_str)
        encrypt = xml_data.get("Encrypt", "")

        if not encrypt:
            logger.warning(
                "WeCom payload missing Encrypt element",
                extra={
                    "event": "wecom_payload_validation",
                    "status": "failed",
                },
            )
            return self.make_invalid_payload_response(is_sync_check)

        # Check timestamp tolerance before decryption
        if not self.validate_timestamp(timestamp):
            return self.make_invalid_payload_response(is_sync_check)

        # Decrypt and parse message
        msg_data = self.decrypt_and_parse_message(
            encrypt, timestamp, nonce, msg_signature
        )

        # Route to appropriate handler based on message type
        if self.is_customer_service_event(msg_data):
            return self.handle_customer_service_event(msg_data, is_sync_check)

        return self.handle_internal_message(msg_data, is_sync_check)


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
            logger.warning(
                "WeCom message delivery failed: missing access token",
                extra={
                    "event": "wecom_message_delivery",
                    "status": "failed",
                    "reason": "missing_access_token",
                },
            )
            return {"is_error": True, "error": "No access token available"}

        target_user = self.to_user
        if not target_user and isinstance(results, dict):
            parser_result = results.get("wecom_events_parser")
            if isinstance(parser_result, dict):
                target_user = parser_result.get("target_user")
        target_chat = self.chat_id
        if not target_user and not target_chat:
            logger.warning(
                "WeCom message delivery failed: missing recipient",
                extra={
                    "event": "wecom_message_delivery",
                    "status": "failed",
                    "reason": "missing_recipient",
                },
            )
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
            logger.warning(
                "WeCom message delivery failed",
                extra={
                    "event": "wecom_message_delivery",
                    "status": "failed",
                    "errcode": errcode,
                    "errmsg": data.get("errmsg", "Unknown error"),
                    "target_user": target_user,
                    "target_chat": target_chat,
                },
            )
            return {
                "is_error": True,
                "errcode": errcode,
                "errmsg": data.get("errmsg", "Unknown error"),
            }

        logger.info(
            "WeCom message delivered",
            extra={
                "event": "wecom_message_delivery",
                "status": "success",
                "errcode": 0,
                "target_user": target_user,
                "target_chat": target_chat,
            },
        )
        return {
            "is_error": False,
            "errcode": 0,
            "errmsg": "ok",
        }


@registry.register(
    NodeMetadata(
        name="WeComGroupPushNode",
        description="Send messages to WeCom group via webhook",
        category="wecom",
    )
)
class WeComGroupPushNode(TaskNode):
    """Send messages to a WeCom group via webhook."""

    webhook_key: str | None = Field(
        default="[[wecom_group_webhook_key]]",
        description="WeCom group webhook key (from Orcheo vault)",
    )
    webhook_url: str | None = Field(
        default=None,
        description="Optional full webhook URL override",
    )
    msg_type: str = Field(
        default="text",
        description="Message type (text or markdown)",
    )
    content: str = Field(description="Message content to send")
    timeout: float | None = Field(
        default=10.0,
        description="Timeout in seconds for the webhook request",
    )

    def build_webhook_url(self) -> str | None:
        """Return the webhook URL from key or explicit URL."""
        if self.webhook_url:
            return self.webhook_url
        if self.webhook_key:
            return (
                "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key="
                f"{self.webhook_key}"
            )
        return None

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Send the webhook payload to WeCom."""
        url = self.build_webhook_url()
        if not url:
            logger.warning(
                "WeCom group webhook missing URL/key",
                extra={
                    "event": "wecom_group_webhook",
                    "status": "failed",
                    "reason": "missing_webhook",
                },
            )
            return {
                "is_error": True,
                "error": "No webhook URL or key provided",
            }

        payload: dict[str, Any] = {"msgtype": self.msg_type}
        if self.msg_type == "markdown":
            payload["markdown"] = {"content": self.content}
        else:
            payload["text"] = {"content": self.content}

        client = httpx.AsyncClient(timeout=self.timeout)
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        finally:
            await client.aclose()

        errcode = data.get("errcode", 0)
        if errcode != 0:
            logger.warning(
                "WeCom group webhook delivery failed",
                extra={
                    "event": "wecom_group_webhook",
                    "status": "failed",
                    "errcode": errcode,
                    "errmsg": data.get("errmsg", "Unknown error"),
                },
            )
            return {
                "is_error": True,
                "errcode": errcode,
                "errmsg": data.get("errmsg", "Unknown error"),
                "status_code": response.status_code,
            }

        logger.info(
            "WeCom group webhook delivered",
            extra={
                "event": "wecom_group_webhook",
                "status": "success",
                "errcode": 0,
            },
        )
        return {
            "is_error": False,
            "errcode": 0,
            "errmsg": data.get("errmsg", "ok"),
            "status_code": response.status_code,
        }


def get_access_token_from_state(results: dict[str, Any]) -> str | None:
    """Extract access token from workflow state results.

    Looks for access_token in common node result keys.
    """
    for key in ("get_access_token", "get_cs_access_token"):
        token_result = results.get(key, {})
        if isinstance(token_result, dict):
            token = token_result.get("access_token")
            if token:
                return token
    return None


@registry.register(
    NodeMetadata(
        name="WeComCustomerServiceSyncNode",
        description="Sync messages from WeCom Customer Service (微信客服)",
        category="wecom",
    )
)
class WeComCustomerServiceSyncNode(TaskNode):
    """Sync messages from WeCom Customer Service (微信客服).

    This node fetches messages from external WeChat users who contact
    the enterprise through Customer Service. It should be used after
    WeComEventsParserNode detects a kf_msg_or_event callback.

    The sync_msg API returns all new messages since the last cursor.
    Only the first text message from external users is processed.

    Requires an access token from a preceding WeComAccessTokenNode
    (named 'get_access_token' or 'get_cs_access_token' in the workflow).
    """

    open_kf_id: str | None = Field(
        default=None,
        description="Customer Service account ID (from parser result)",
    )
    kf_token: str | None = Field(
        default=None,
        description="Sync token from callback (from parser result)",
    )
    cursor: str | None = Field(
        default=None,
        description="Optional cursor for pagination",
    )
    limit: int = Field(
        default=100,
        description="Maximum number of messages to fetch (1-1000)",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Sync messages from Customer Service."""
        results = state.get("results", {})
        parser_result = results.get("wecom_events_parser", {})

        # Get access token from state (requires preceding WeComAccessTokenNode)
        access_token = get_access_token_from_state(results)
        if not access_token:
            logger.warning(
                "WeCom CS sync failed: missing access token",
                extra={
                    "event": "wecom_cs_sync",
                    "status": "failed",
                    "reason": "missing_access_token",
                },
            )
            return {"is_error": True, "error": "No access token available"}

        open_kf_id = self.open_kf_id or parser_result.get("open_kf_id", "")
        kf_token = self.kf_token or parser_result.get("kf_token", "")

        if not open_kf_id:
            logger.warning(
                "WeCom CS sync failed: missing open_kf_id",
                extra={
                    "event": "wecom_cs_sync",
                    "status": "failed",
                    "reason": "missing_open_kf_id",
                },
            )
            return {"is_error": True, "error": "No open_kf_id provided"}

        # Sync messages
        url = "https://qyapi.weixin.qq.com/cgi-bin/kf/sync_msg"
        params = {"access_token": access_token}
        payload: dict[str, Any] = {
            "open_kfid": open_kf_id,
            "limit": min(self.limit, 1000),
        }
        if kf_token:
            payload["token"] = kf_token
        if self.cursor:
            payload["cursor"] = self.cursor

        client = httpx.AsyncClient(timeout=10.0)
        try:
            response = await client.post(url, params=params, json=payload)
            response.raise_for_status()
            data = response.json()
        finally:
            await client.aclose()

        errcode = data.get("errcode", 0)
        if errcode != 0:
            logger.warning(
                "WeCom CS sync failed",
                extra={
                    "event": "wecom_cs_sync",
                    "status": "failed",
                    "errcode": errcode,
                    "errmsg": data.get("errmsg", "Unknown error"),
                },
            )
            return {
                "is_error": True,
                "errcode": errcode,
                "errmsg": data.get("errmsg", "Unknown error"),
            }

        msg_list = data.get("msg_list", [])
        next_cursor = data.get("next_cursor", "")
        has_more = data.get("has_more", 0) == 1

        # Find the most recent text message from an external user
        # Messages are returned oldest-first, so reverse to get newest first
        external_user_id = ""
        content = ""
        for msg in reversed(msg_list):
            # origin: 3=external WeChat user, 4=system, 5=internal user
            if msg.get("origin") == 3 and msg.get("msgtype") == "text":
                external_user_id = msg.get("external_userid", "")
                text_data = msg.get("text", {})
                content = text_data.get("content", "")
                if content:
                    break

        return {
            "is_error": False,
            "open_kf_id": open_kf_id,
            "external_user_id": external_user_id,
            "content": content,
            "message_count": len(msg_list),
            "next_cursor": next_cursor,
            "has_more": has_more,
            "should_process": bool(external_user_id and content),
        }


@registry.register(
    NodeMetadata(
        name="WeComCustomerServiceSendNode",
        description="Send messages via WeCom Customer Service (微信客服)",
        category="wecom",
    )
)
class WeComCustomerServiceSendNode(TaskNode):
    """Send messages via WeCom Customer Service (微信客服).

    This node sends messages to external WeChat users through Customer
    Service. It should be used after WeComCustomerServiceSyncNode has
    fetched the external user ID.

    Requires an access token from a preceding WeComAccessTokenNode
    (named 'get_access_token' or 'get_cs_access_token' in the workflow).
    """

    open_kf_id: str | None = Field(
        default=None,
        description="Customer Service account ID",
    )
    external_user_id: str | None = Field(
        default=None,
        description="External WeChat user ID",
    )
    message: str = Field(description="Message content to send")
    msg_type: str = Field(default="text", description="Message type (text only)")

    async def send_message(
        self,
        access_token: str,
        external_user_id: str,
        open_kf_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Send a customer service message."""
        url = "https://qyapi.weixin.qq.com/cgi-bin/kf/send_msg"
        params: dict[str, str] = {"access_token": access_token}

        client = httpx.AsyncClient(timeout=10.0)
        try:
            response = await client.post(url, params=params, json=payload)
            response.raise_for_status()
            data = response.json()
        finally:
            await client.aclose()

        errcode = data.get("errcode", 0)
        errmsg = data.get("errmsg", "Unknown error")
        if errcode != 0:
            logger.warning(
                "WeCom CS send failed: errcode=%s errmsg=%s",
                errcode,
                errmsg,
                extra={
                    "event": "wecom_cs_send",
                    "status": "failed",
                    "errcode": errcode,
                    "errmsg": errmsg,
                    "external_user_id": external_user_id,
                },
            )
            return {
                "is_error": True,
                "errcode": errcode,
                "errmsg": data.get("errmsg", "Unknown error"),
            }

        logger.info(
            "WeCom CS message delivered",
            extra={
                "event": "wecom_cs_send",
                "status": "success",
                "errcode": 0,
                "external_user_id": external_user_id,
                "msgid": data.get("msgid"),
            },
        )
        return {
            "is_error": False,
            "errcode": 0,
            "errmsg": "ok",
            "msgid": data.get("msgid"),
        }

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Send message via Customer Service."""
        results = state.get("results", {})
        sync_result = results.get("wecom_cs_sync", {})
        parser_result = results.get("wecom_events_parser", {})

        # Get access token from state (requires preceding WeComAccessTokenNode)
        access_token = get_access_token_from_state(results)
        if not access_token:
            logger.warning(
                "WeCom CS send failed: missing access token",
                extra={
                    "event": "wecom_cs_send",
                    "status": "failed",
                    "reason": "missing_access_token",
                },
            )
            return {"is_error": True, "error": "No access token available"}

        open_kf_id = (
            self.open_kf_id
            or sync_result.get("open_kf_id")
            or parser_result.get("open_kf_id", "")
        )
        external_user_id = self.external_user_id or sync_result.get(
            "external_user_id", ""
        )

        if not open_kf_id:
            logger.warning(
                "WeCom CS send failed: missing open_kf_id",
                extra={
                    "event": "wecom_cs_send",
                    "status": "failed",
                    "reason": "missing_open_kf_id",
                },
            )
            return {"is_error": True, "error": "No open_kf_id provided"}

        if not external_user_id:
            logger.warning(
                "WeCom CS send failed: missing external_user_id",
                extra={
                    "event": "wecom_cs_send",
                    "status": "failed",
                    "reason": "missing_external_user_id",
                },
            )
            return {"is_error": True, "error": "No external_user_id provided"}

        payload: dict[str, Any] = {
            "touser": external_user_id,
            "open_kfid": open_kf_id,
            "msgtype": self.msg_type,
        }

        if self.msg_type == "text":
            payload["text"] = {"content": self.message}
        else:
            # Only text is currently supported
            payload["text"] = {"content": self.message}

        return await self.send_message(
            access_token, external_user_id, open_kf_id, payload
        )


__all__ = [
    "WeComAccessTokenNode",
    "WeComCustomerServiceSendNode",
    "WeComCustomerServiceSyncNode",
    "WeComEventsParserNode",
    "WeComGroupPushNode",
    "WeComSendMessageNode",
]
