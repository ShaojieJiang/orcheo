"""Codex workflow node."""

from __future__ import annotations
from orcheo.nodes.external_agent import ExternalAgentNode
from orcheo.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="CodexNode",
        description="Execute Codex as a non-interactive coding-agent step.",
        category="ai",
    )
)
class CodexNode(ExternalAgentNode):
    """Workflow node for the Codex CLI."""

    provider_name = "codex"
