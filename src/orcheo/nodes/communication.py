"""Communication nodes covering email and Discord webhooks."""

from __future__ import annotations
import asyncio
import smtplib
from email.message import EmailMessage
from typing import Any
import httpx
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="EmailNode",
        description="Send an email via SMTP with optional TLS and authentication.",
        category="communication",
    )
)
class EmailNode(TaskNode):
    """Node for dispatching email messages via SMTP."""

    smtp_host: str = Field(default="localhost", description="SMTP server host")
    smtp_port: int = Field(default=587, description="SMTP server port")
    use_tls: bool = Field(
        default=True,
        description="Upgrade the connection using STARTTLS",
    )
    username: str | None = Field(default=None, description="Optional SMTP username")
    password: str | None = Field(default=None, description="Optional SMTP password")
    from_address: str = Field(description="Sender email address")
    to_addresses: list[str] = Field(
        default_factory=list, description="List of recipient email addresses"
    )
    cc_addresses: list[str] | None = Field(
        default=None, description="Optional CC recipient email addresses"
    )
    bcc_addresses: list[str] | None = Field(
        default=None, description="Optional BCC recipient email addresses"
    )
    subject: str = Field(default="", description="Email subject line")
    body: str = Field(default="", description="Email body content")
    subtype: str = Field(
        default="plain", description="Email body subtype (plain or html)"
    )
    timeout: float | None = Field(
        default=30.0,
        description="Timeout in seconds for SMTP operations",
    )

    def _build_message(self) -> tuple[EmailMessage, list[str]]:
        message = EmailMessage()
        message["Subject"] = self.subject
        message["From"] = self.from_address
        message["To"] = ", ".join(self.to_addresses)
        if self.cc_addresses:
            message["Cc"] = ", ".join(self.cc_addresses)
        recipients = list(self.to_addresses)
        if self.cc_addresses:
            recipients.extend(self.cc_addresses)
        if self.bcc_addresses:
            recipients.extend(self.bcc_addresses)
        message.set_content(self.body, subtype=self.subtype)
        return message, recipients

    def _send_email(self) -> dict[str, Any]:
        message, recipients = self._build_message()
        timeout = self.timeout if self.timeout is not None else 30.0
        with smtplib.SMTP(
            self.smtp_host,
            self.smtp_port,
            timeout=timeout,
        ) as client:
            if self.use_tls:
                client.starttls()
            if self.username and self.password:
                client.login(self.username, self.password)
            refused = client.send_message(message, to_addrs=recipients)
        accepted = [
            address for address in recipients if not refused or address not in refused
        ]
        return {"accepted": accepted, "refused": refused}

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Dispatch the email message."""
        if not self.to_addresses and not self.cc_addresses and not self.bcc_addresses:
            msg = "At least one recipient must be specified"
            raise ValueError(msg)
        return await asyncio.to_thread(self._send_email)


@registry.register(
    NodeMetadata(
        name="DiscordWebhookNode",
        description="Send messages to Discord via incoming webhooks.",
        category="communication",
    )
)
class DiscordWebhookNode(TaskNode):
    """Node that posts messages to a Discord webhook URL."""

    webhook_url: str = Field(description="Discord webhook URL")
    content: str | None = Field(default=None, description="Message content to send")
    username: str | None = Field(
        default=None, description="Override username displayed in Discord"
    )
    avatar_url: str | None = Field(
        default=None, description="Override avatar URL displayed in Discord"
    )
    embeds: list[dict[str, Any]] | None = Field(
        default=None, description="Optional embeds payload"
    )
    tts: bool = Field(default=False, description="Enable text-to-speech announcement")
    timeout: float | None = Field(
        default=10.0,
        description="Timeout in seconds for the webhook request",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Send the webhook payload to Discord."""
        payload: dict[str, Any] = {"tts": self.tts}
        if self.content is not None:
            payload["content"] = self.content
        if self.username is not None:
            payload["username"] = self.username
        if self.avatar_url is not None:
            payload["avatar_url"] = self.avatar_url
        if self.embeds is not None:
            payload["embeds"] = self.embeds

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.webhook_url, json=payload)
            response.raise_for_status()

        return {
            "status_code": response.status_code,
            "reason": response.reason_phrase,
        }


__all__ = ["EmailNode", "DiscordWebhookNode"]
