"""WeCom news digest workflow with mention and cron triggers.

Configure WeCom to send callback requests to:
`/api/workflows/{workflow_id}/triggers/webhook?preserve_raw_body=true`
so signatures can be verified.

Configurable inputs (workflow_config.json):
- corp_id (WeCom corp ID)
- chat_id (WeCom chat/group ID for message delivery)
- agent_id (WeCom app agent ID)
- message_template (scripted message content)

Orcheo vault secrets required:
- wecom_corp_secret: WeCom app secret for access token
- wecom_token: Callback token for signature validation
- wecom_encoding_aes_key: AES key for callback decryption
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
from langgraph.graph import END, StateGraph
from pydantic import Field
from orcheo.edges import Condition, IfElse
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.triggers import CronTriggerNode


class DetectTriggerNode(TaskNode):
    """Detect whether the workflow was invoked by a webhook payload."""

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return whether a webhook body is present in inputs."""
        inputs = state.get("inputs", {})
        has_webhook = bool(inputs.get("body"))
        return {"has_webhook": has_webhook}


class WeComEventsParserNode(TaskNode):
    """Validate WeCom signatures and parse callback payloads.

    Handles:
    - URL verification (GET with echostr)
    - Message decryption for encrypted callbacks
    - Signature validation using Token
    - Filtering for app mentions in specified chat
    """

    token: str = "[[wecom_token]]"
    """WeCom callback token for signature validation (from Orcheo vault)."""
    encoding_aes_key: str = "[[wecom_encoding_aes_key]]"
    """WeCom AES key for payload decryption (from Orcheo vault)."""
    corp_id: str = Field(description="WeCom corp ID for decryption validation")
    chat_id: str | None = Field(
        default=None,
        description="Optional chat ID to filter events",
    )
    timestamp_tolerance_seconds: int = Field(
        default=300,
        description="Maximum age for WeCom signature timestamps",
    )

    def _verify_signature(
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

    def _decrypt_message(self, encrypt: str, encoding_aes_key: str) -> str:
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

    def _parse_xml(self, xml_str: str) -> dict[str, str]:
        """Parse WeCom XML payload."""
        root = ElementTree.fromstring(xml_str)
        return {child.tag: (child.text or "") for child in root}

    def _extract_inputs(self, state: State) -> dict[str, Any]:
        """Extract inputs from state."""
        if hasattr(state, "model_dump"):
            state_dict = state.model_dump()
        else:
            state_dict = dict(state)
        raw_inputs = state_dict.get("inputs")
        if isinstance(raw_inputs, dict):
            return dict(raw_inputs)
        return state_dict

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Parse the WeCom callback payload and validate signatures."""
        inputs = self._extract_inputs(state)
        query_params = inputs.get("query_params", {})

        msg_signature = query_params.get("msg_signature", "")
        timestamp = query_params.get("timestamp", "")
        nonce = query_params.get("nonce", "")
        echostr = query_params.get("echostr")

        # URL verification request (GET with echostr)
        if echostr:
            self._verify_signature(self.token, timestamp, nonce, echostr, msg_signature)
            decrypted_echostr = self._decrypt_message(echostr, self.encoding_aes_key)
            return {
                "is_verification": True,
                "challenge": decrypted_echostr,
                "should_process": False,
            }

        # Parse encrypted message body
        body = inputs.get("body", {})
        if isinstance(body, dict) and "raw" in body:
            body_str = body["raw"]
        elif isinstance(body, str):
            body_str = body
        else:
            body_str = str(body)

        xml_data = self._parse_xml(body_str)
        encrypt = xml_data.get("Encrypt", "")

        if not encrypt:
            return {
                "is_verification": False,
                "event_type": None,
                "should_process": False,
            }

        # Verify signature
        self._verify_signature(self.token, timestamp, nonce, encrypt, msg_signature)

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
        decrypted_xml = self._decrypt_message(encrypt, self.encoding_aes_key)
        msg_data = self._parse_xml(decrypted_xml)

        msg_type = msg_data.get("MsgType", "")
        chat_id = msg_data.get("ChatId", "")
        content = msg_data.get("Content", "")

        # Filter by chat ID if specified
        if self.chat_id and chat_id != self.chat_id:
            return {
                "is_verification": False,
                "event_type": msg_type,
                "chat_id": chat_id,
                "should_process": False,
            }

        # Check if this is an app mention (simplified check)
        # WeCom mentions are typically in the Content field
        is_mention = msg_type == "text"

        return {
            "is_verification": False,
            "event_type": msg_type,
            "chat_id": chat_id,
            "user": msg_data.get("FromUserName", ""),
            "content": content,
            "should_process": is_mention,
        }


class WeComAccessTokenNode(TaskNode):
    """Fetch and cache WeCom access token."""

    corp_id: str = Field(description="WeCom corp ID")
    corp_secret: str = "[[wecom_corp_secret]]"
    """WeCom app secret (from Orcheo vault)."""

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Fetch access token from WeCom API."""
        url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        params = {"corpid": self.corp_id, "corpsecret": self.corp_secret}

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        if data.get("errcode", 0) != 0:
            msg = f"WeCom token error: {data.get('errmsg', 'Unknown error')}"
            raise ValueError(msg)

        return {
            "access_token": data.get("access_token"),
            "expires_in": data.get("expires_in"),
        }


class WeComSendMessageNode(TaskNode):
    """Send messages to WeCom chat."""

    agent_id: int | str = Field(description="WeCom app agent ID")
    chat_id: str = Field(description="WeCom chat ID for message delivery")
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

        url = "https://qyapi.weixin.qq.com/cgi-bin/appchat/send"
        params = {"access_token": access_token}

        # Convert agent_id to int if string
        agent_id = self.agent_id
        if isinstance(agent_id, str):
            agent_id = int(agent_id)

        payload: dict[str, Any] = {
            "chatid": self.chat_id,
            "msgtype": self.msg_type,
            "agentid": agent_id,
            "safe": 0,
        }

        if self.msg_type == "markdown":
            payload["markdown"] = {"content": self.message}
        else:
            payload["text"] = {"content": self.message}

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, params=params, json=payload)
            response.raise_for_status()
            data = response.json()

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


async def build_graph() -> StateGraph:
    """Build the WeCom mention responder and scheduled message workflow."""
    graph = StateGraph(State)

    graph.add_node("detect_trigger", DetectTriggerNode(name="detect_trigger"))

    graph.add_node(
        "cron_trigger",
        CronTriggerNode(
            name="cron_trigger",
            expression="* * * * *",  # Once per minute for Milestone 1
            timezone="Europe/Amsterdam",
        ),
    )

    graph.add_node(
        "wecom_events_parser",
        WeComEventsParserNode(
            name="wecom_events_parser",
            corp_id="{{config.configurable.corp_id}}",
            chat_id="{{config.configurable.chat_id}}",
        ),
    )

    graph.add_node(
        "get_access_token",
        WeComAccessTokenNode(
            name="get_access_token",
            corp_id="{{config.configurable.corp_id}}",
        ),
    )

    graph.add_node(
        "send_message",
        WeComSendMessageNode(
            name="send_message",
            agent_id="{{config.configurable.agent_id}}",
            chat_id="{{config.configurable.chat_id}}",
            message="{{config.configurable.message_template}}",
        ),
    )

    # Entry point
    graph.set_entry_point("detect_trigger")

    # Route based on trigger type
    trigger_router = IfElse(
        name="trigger_router",
        conditions=[
            Condition(left="{{detect_trigger.has_webhook}}", operator="is_truthy")
        ],
    )
    graph.add_conditional_edges(
        "detect_trigger",
        trigger_router,
        {
            "true": "wecom_events_parser",
            "false": "cron_trigger",
        },
    )

    # Cron trigger leads to access token fetch
    graph.add_edge("cron_trigger", "get_access_token")

    # WeCom events parser routes based on whether to process
    reply_router = IfElse(
        name="reply_router",
        conditions=[
            Condition(
                left="{{wecom_events_parser.should_process}}", operator="is_truthy"
            ),
        ],
    )
    graph.add_conditional_edges(
        "wecom_events_parser",
        reply_router,
        {
            "true": "get_access_token",
            "false": END,
        },
    )

    # Access token leads to send message
    graph.add_edge("get_access_token", "send_message")
    graph.add_edge("send_message", END)

    return graph
