"""Claude Code workflow node."""

from __future__ import annotations
from orcheo.nodes.external_agent import ExternalAgentNode
from orcheo.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="ClaudeCodeNode",
        description="Execute Claude Code as a non-interactive coding-agent step.",
        category="ai",
    )
)
class ClaudeCodeNode(ExternalAgentNode):
    """Workflow node for the Claude Code CLI."""

    provider_name = "claude_code"
