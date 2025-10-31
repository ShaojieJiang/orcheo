"""Node registry and metadata definitions for Orcheo."""

from orcheo.nodes.ai import Agent
from orcheo.nodes.code import PythonCode
from orcheo.nodes.communication import DiscordWebhookNode, EmailNode
from orcheo.nodes.data import (
    DataTransformNode,
    HttpRequestNode,
    JsonProcessingNode,
    MergeNode,
)
from orcheo.nodes.logic import (
    DelayNode,
    IfElseNode,
    SetVariableNode,
    SwitchNode,
    WhileNode,
)
from orcheo.nodes.mongodb import MongoDBNode
from orcheo.nodes.registry import NodeMetadata, NodeRegistry, registry
from orcheo.nodes.slack import SlackNode
from orcheo.nodes.storage import PostgresNode, SQLiteNode
from orcheo.nodes.telegram import MessageTelegram
from orcheo.nodes.triggers import (
    CronTriggerNode,
    HttpPollingTriggerNode,
    ManualTriggerNode,
    WebhookTriggerNode,
)
from orcheo.nodes.utility import (
    DebugNode,
    JavaScriptSandboxNode,
    PythonSandboxNode,
    SubWorkflowNode,
)


__all__ = [
    "NodeMetadata",
    "NodeRegistry",
    "registry",
    "Agent",
    "PythonCode",
    "HttpRequestNode",
    "JsonProcessingNode",
    "DataTransformNode",
    "MergeNode",
    "IfElseNode",
    "SwitchNode",
    "WhileNode",
    "SetVariableNode",
    "DelayNode",
    "MongoDBNode",
    "PostgresNode",
    "SQLiteNode",
    "SlackNode",
    "EmailNode",
    "DiscordWebhookNode",
    "MessageTelegram",
    "PythonSandboxNode",
    "JavaScriptSandboxNode",
    "DebugNode",
    "SubWorkflowNode",
    "WebhookTriggerNode",
    "CronTriggerNode",
    "ManualTriggerNode",
    "HttpPollingTriggerNode",
]
