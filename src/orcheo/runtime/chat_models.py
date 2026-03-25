"""Helpers for provider-aware chat model initialization."""

from __future__ import annotations
from collections.abc import Mapping
from typing import Any
from orcheo.runtime.credentials import (
    CredentialReferenceNotFoundError,
    DuplicateCredentialReferenceError,
    UnknownCredentialPayloadError,
    credential_ref,
    get_active_credential_resolver,
)


_MODEL_PREFIX_TO_PROVIDER: dict[str, str] = {
    "gpt-": "openai",
    "o1": "openai",
    "o3": "openai",
    "o4": "openai",
    "claude": "anthropic",
    "command": "cohere",
    "deepseek": "deepseek",
    "grok": "xai",
    "mistral": "mistralai",
    "sonar": "perplexity",
}

_PROVIDER_SECRET_NAMES: dict[str, str] = {
    "anthropic": "anthropic_api_key",
    "azure_openai": "azure_openai_api_key",
    "cohere": "cohere_api_key",
    "deepseek": "deepseek_api_key",
    "fireworks": "fireworks_api_key",
    "google_genai": "google_api_key",
    "groq": "groq_api_key",
    "mistralai": "mistralai_api_key",
    "openai": "openai_api_key",
    "perplexity": "perplexity_api_key",
    "together": "together_api_key",
    "xai": "xai_api_key",
}


def normalize_chat_model_kwargs(
    ai_model: str | None,
    model_kwargs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return chat-model kwargs with provider-specific auth normalized."""
    normalized = dict(model_kwargs or {})
    provider_key_values = _pop_provider_key_aliases(normalized)

    api_key = normalized.get("api_key")
    if isinstance(api_key, str) and api_key.strip():
        return normalized

    provider = _resolve_provider(ai_model, normalized)
    if provider is None:
        return normalized

    explicit_provider_key = provider_key_values.get(provider)
    if isinstance(explicit_provider_key, str):
        explicit_provider_key = explicit_provider_key.strip()
        if explicit_provider_key:
            normalized["api_key"] = explicit_provider_key
            return normalized

    resolved_api_key = _resolve_provider_api_key(provider)
    if resolved_api_key:
        normalized["api_key"] = resolved_api_key
    return normalized


def _resolve_provider(
    ai_model: str | None,
    model_kwargs: Mapping[str, Any],
) -> str | None:
    provider = model_kwargs.get("model_provider")
    if isinstance(provider, str):
        normalized_provider = provider.strip()
        if normalized_provider:
            return normalized_provider

    if not isinstance(ai_model, str):
        return None
    normalized_model = ai_model.strip()
    if not normalized_model:
        return None
    if ":" in normalized_model:
        provider_name, _model = normalized_model.split(":", 1)
        provider_name = provider_name.strip()
        return provider_name or None

    folded = normalized_model.casefold()
    for prefix, provider_name in _MODEL_PREFIX_TO_PROVIDER.items():
        if folded.startswith(prefix):
            return provider_name
    return None


def _resolve_provider_api_key(provider: str) -> str | None:
    resolver = get_active_credential_resolver()
    credential_name = _PROVIDER_SECRET_NAMES.get(provider)
    if resolver is not None and credential_name is not None:
        try:
            resolved = resolver.resolve(credential_ref(credential_name))
        except (
            CredentialReferenceNotFoundError,
            DuplicateCredentialReferenceError,
            UnknownCredentialPayloadError,
        ):
            resolved = None
        if isinstance(resolved, str):
            secret = resolved.strip()
            if secret:
                return secret

    return None


def _pop_provider_key_aliases(model_kwargs: dict[str, Any]) -> dict[str, Any]:
    """Remove provider-specific API key aliases and return their values."""
    aliases: dict[str, Any] = {}
    for provider, secret_name in _PROVIDER_SECRET_NAMES.items():
        if secret_name in model_kwargs:
            aliases[provider] = model_kwargs.pop(secret_name)
    return aliases


__all__ = ["normalize_chat_model_kwargs"]
