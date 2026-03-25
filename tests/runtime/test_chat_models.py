"""Tests for provider-aware chat model kwargs normalization."""

from __future__ import annotations
import pytest
from orcheo.runtime.chat_models import normalize_chat_model_kwargs


def test_normalize_chat_model_kwargs_prefers_explicit_api_key() -> None:
    result = normalize_chat_model_kwargs(
        "deepseek:deepseek-chat",
        {"api_key": "explicit-key", "deepseek_api_key": "provider-key"},
    )

    assert result["api_key"] == "explicit-key"
    assert "deepseek_api_key" not in result


def test_normalize_chat_model_kwargs_promotes_provider_specific_alias() -> None:
    result = normalize_chat_model_kwargs(
        "deepseek:deepseek-chat",
        {
            "deepseek_api_key": "deepseek-secret",
            "openai_api_key": "openai-secret",
            "temperature": 0.1,
        },
    )

    assert result["api_key"] == "deepseek-secret"
    assert result["temperature"] == 0.1
    assert "deepseek_api_key" not in result
    assert "openai_api_key" not in result


def test_normalize_chat_model_kwargs_uses_active_credential_resolver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StubResolver:
        def resolve(self, reference: object) -> str:
            assert getattr(reference, "identifier", None) == "deepseek_api_key"
            return "resolved-from-vault"

    monkeypatch.setattr(
        "orcheo.runtime.chat_models.get_active_credential_resolver",
        lambda: StubResolver(),
    )

    result = normalize_chat_model_kwargs("deepseek:deepseek-chat")

    assert result["api_key"] == "resolved-from-vault"


def test_normalize_chat_model_kwargs_leaves_api_key_unset_without_alias_or_resolver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "orcheo.runtime.chat_models.get_active_credential_resolver",
        lambda: None,
    )

    result = normalize_chat_model_kwargs("deepseek:deepseek-chat")

    assert "api_key" not in result


def test_normalize_chat_model_kwargs_infers_openai_provider_from_model_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StubResolver:
        def resolve(self, reference: object) -> str:
            assert getattr(reference, "identifier", None) == "openai_api_key"
            return "resolved-openai-key"

    monkeypatch.setattr(
        "orcheo.runtime.chat_models.get_active_credential_resolver",
        lambda: StubResolver(),
    )

    result = normalize_chat_model_kwargs("gpt-4.1")

    assert result["api_key"] == "resolved-openai-key"


def test_normalize_chat_model_kwargs_preserves_aliases_when_provider_unknown() -> None:
    result = normalize_chat_model_kwargs(
        "accounts/fireworks/models/llama-v3p1-8b-instruct",
        {"fireworks_api_key": "fireworks-secret"},
    )

    assert result["fireworks_api_key"] == "fireworks-secret"
    assert "api_key" not in result
