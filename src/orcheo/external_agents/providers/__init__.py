"""Provider adapters for external agent runtimes."""

from orcheo.external_agents.providers.base import ExternalAgentProvider
from orcheo.external_agents.providers.claude_code import ClaudeCodeProvider
from orcheo.external_agents.providers.codex import CodexProvider


DEFAULT_PROVIDERS: dict[str, ExternalAgentProvider] = {
    "claude_code": ClaudeCodeProvider(),
    "codex": CodexProvider(),
}


__all__ = [
    "DEFAULT_PROVIDERS",
    "ExternalAgentProvider",
    "ClaudeCodeProvider",
    "CodexProvider",
]
