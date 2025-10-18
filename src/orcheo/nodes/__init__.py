"""Node registry and metadata definitions for Orcheo."""

from orcheo.nodes import communication as _communication_nodes  # noqa: F401
from orcheo.nodes import data as _data_nodes  # noqa: F401
from orcheo.nodes import logic as _logic_nodes  # noqa: F401
from orcheo.nodes.ai import (
    Agent,
    AnthropicChat,
    CustomAgent,
    OpenAIChat,
    TextProcessing,
)
from orcheo.nodes.code import PythonCode
from orcheo.nodes.communication import DiscordMessage, EmailNotification
from orcheo.nodes.data import DataTransform, HttpRequest, JsonExtractor
from orcheo.nodes.logic import Guardrails, MergeDictionaries, SetVariable
from orcheo.nodes.registry import NodeMetadata, NodeRegistry, registry
from orcheo.nodes.telegram import MessageTelegram


__all__ = [
    "NodeMetadata",
    "NodeRegistry",
    "registry",
    "Agent",
    "OpenAIChat",
    "AnthropicChat",
    "CustomAgent",
    "TextProcessing",
    "PythonCode",
    "MessageTelegram",
    "HttpRequest",
    "JsonExtractor",
    "DataTransform",
    "SetVariable",
    "MergeDictionaries",
    "Guardrails",
    "EmailNotification",
    "DiscordMessage",
]
