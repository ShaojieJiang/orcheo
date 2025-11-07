"""Node registry and metadata definitions for Orcheo."""

from orcheo.nodes.ai import AgentNode
from orcheo.nodes.code import PythonCode
from orcheo.nodes.communication import DiscordWebhookNode, EmailNode
from orcheo.nodes.data import (
    DataTransformNode,
    HttpRequestNode,
    JsonProcessingNode,
    MergeNode,
)
from orcheo.nodes.debug import DebugNode
from orcheo.nodes.javascript_sandbox import JavaScriptSandboxNode
from orcheo.nodes.logic import (
    DelayNode,
    IfElseNode,
    SetVariableNode,
    SwitchNode,
    WhileNode,
)
from orcheo.nodes.mongodb import MongoDBNode
from orcheo.nodes.python_sandbox import PythonSandboxNode
from orcheo.nodes.registry import NodeMetadata, NodeRegistry, registry
from orcheo.nodes.slack import SlackNode
from orcheo.nodes.storage import PostgresNode, SQLiteNode
from orcheo.nodes.sub_workflow import SubWorkflowNode
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
    "AgentNode",
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
