"""Node registry and metadata definitions for Orcheo."""

from orcheo.nodes.agentensor import AgentensorNode
from orcheo.nodes.ai import AgentNode, AgentReplyExtractorNode, LLMNode
from orcheo.nodes.communication import DiscordWebhookNode, EmailNode
from orcheo.nodes.conversational_search import (
    ChunkEmbeddingNode,
    ChunkingStrategyNode,
    DocumentLoaderNode,
    InMemoryVectorStore,
    MetadataExtractorNode,
    PineconeVectorStore,
    TextEmbeddingNode,
    VectorStoreUpsertNode,
)
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
    ForLoopNode,
    SetVariableNode,
)
from orcheo.nodes.mongodb import (
    MongoDBAggregateNode,
    MongoDBEnsureSearchIndexNode,
    MongoDBEnsureVectorIndexNode,
    MongoDBFindNode,
    MongoDBHybridSearchNode,
    MongoDBInsertManyNode,
    MongoDBNode,
    MongoDBUpdateManyNode,
    MongoDBUpsertManyNode,
)
from orcheo.nodes.registry import NodeMetadata, NodeRegistry, registry
from orcheo.nodes.slack import SlackEventsParserNode, SlackNode
from orcheo.nodes.storage import PostgresNode, SQLiteNode
from orcheo.nodes.sub_workflow import SubWorkflowNode
from orcheo.nodes.telegram import MessageTelegram, TelegramEventsParserNode
from orcheo.nodes.triggers import (
    CronTriggerNode,
    HttpPollingTriggerNode,
    ManualTriggerNode,
    WebhookTriggerNode,
)
from orcheo.nodes.wecom import (
    WeComAccessTokenNode,
    WeComEventsParserNode,
    WeComSendMessageNode,
)


__all__ = [
    "NodeMetadata",
    "NodeRegistry",
    "registry",
    "AgentNode",
    "AgentReplyExtractorNode",
    "LLMNode",
    "AgentensorNode",
    "HttpRequestNode",
    "JsonProcessingNode",
    "DataTransformNode",
    "MergeNode",
    "SetVariableNode",
    "DelayNode",
    "ForLoopNode",
    "MongoDBNode",
    "MongoDBAggregateNode",
    "MongoDBFindNode",
    "MongoDBInsertManyNode",
    "MongoDBUpdateManyNode",
    "MongoDBUpsertManyNode",
    "MongoDBEnsureSearchIndexNode",
    "MongoDBEnsureVectorIndexNode",
    "MongoDBHybridSearchNode",
    "PostgresNode",
    "SQLiteNode",
    "SlackNode",
    "SlackEventsParserNode",
    "EmailNode",
    "DiscordWebhookNode",
    "MessageTelegram",
    "TelegramEventsParserNode",
    "JavaScriptSandboxNode",
    "DebugNode",
    "SubWorkflowNode",
    "WebhookTriggerNode",
    "CronTriggerNode",
    "ManualTriggerNode",
    "HttpPollingTriggerNode",
    "DocumentLoaderNode",
    "ChunkEmbeddingNode",
    "ChunkingStrategyNode",
    "MetadataExtractorNode",
    "TextEmbeddingNode",
    "VectorStoreUpsertNode",
    "InMemoryVectorStore",
    "PineconeVectorStore",
    "WeComAccessTokenNode",
    "WeComEventsParserNode",
    "WeComSendMessageNode",
]
