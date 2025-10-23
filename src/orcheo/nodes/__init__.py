"""Node registry and metadata definitions for Orcheo."""

from orcheo.nodes.ai import Agent
from orcheo.nodes.code import PythonCode
from orcheo.nodes.logic import (
    DelayNode,
    IfElseNode,
    SetVariableNode,
    SwitchNode,
    WhileNode,
)
from orcheo.nodes.registry import NodeMetadata, NodeRegistry, registry
from orcheo.nodes.telegram import MessageTelegram
from orcheo.nodes.triggers import (
    CronTriggerNode,
    HttpPollingTriggerNode,
    ManualTriggerNode,
    WebhookTriggerNode,
)


__all__ = [
    "NodeMetadata",
    "NodeRegistry",
    "registry",
    "Agent",
    "PythonCode",
    "IfElseNode",
    "SwitchNode",
    "WhileNode",
    "SetVariableNode",
    "DelayNode",
    "MessageTelegram",
    "WebhookTriggerNode",
    "CronTriggerNode",
    "ManualTriggerNode",
    "HttpPollingTriggerNode",
]
