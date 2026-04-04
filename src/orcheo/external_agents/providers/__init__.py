"""Provider adapters for external agent runtimes."""

from orcheo.external_agents.providers.base import ExternalAgentProvider
from orcheo.external_agents.providers.claude_code import ClaudeCodeProvider
from orcheo.external_agents.providers.codex import CodexProvider
from orcheo.external_agents.providers.gemini import GeminiProvider


DEFAULT_PROVIDERS: dict[str, ExternalAgentProvider] = {
    "claude_code": ClaudeCodeProvider(),
    "codex": CodexProvider(),
    "gemini": GeminiProvider(),
}


__all__ = [
    "DEFAULT_PROVIDERS",
    "ExternalAgentProvider",
    "ClaudeCodeProvider",
    "CodexProvider",
    "GeminiProvider",
]
