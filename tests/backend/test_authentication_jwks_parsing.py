"""JWKS parsing tests split from the extended suite."""

from __future__ import annotations
import pytest
from tests.backend.authentication_test_utils import reset_auth_state


@pytest.fixture(autouse=True)
def _reset_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure authentication state is cleared between tests."""

    yield from reset_auth_state(monkeypatch)


def test_parse_jwks_from_string() -> None:
    """_parse_jwks handles JSON string configurations."""
    import json
    from orcheo_backend.app.authentication import _parse_jwks

    jwks_dict = {
        "keys": [
            {"kty": "RSA", "kid": "key1"},
            {"kty": "RSA", "kid": "key2"},
        ]
    }
    jwks_str = json.dumps(jwks_dict)

    keys = _parse_jwks(jwks_str)
    assert len(keys) == 2
    assert keys[0]["kid"] == "key1"


def test_parse_jwks_from_dict() -> None:
    """_parse_jwks handles dictionary configurations."""
    from orcheo_backend.app.authentication import _parse_jwks

    jwks_dict = {
        "keys": [
            {"kty": "RSA", "kid": "key1"},
        ]
    }

    keys = _parse_jwks(jwks_dict)
    assert len(keys) == 1


def test_parse_jwks_from_list() -> None:
    """_parse_jwks handles list configurations."""
    from orcheo_backend.app.authentication import _parse_jwks

    jwks_list = [
        {"kty": "RSA", "kid": "key1"},
        {"kty": "RSA", "kid": "key2"},
    ]

    keys = _parse_jwks(jwks_list)
    assert len(keys) == 2


def test_parse_jwks_invalid_json(caplog: pytest.LogCaptureFixture) -> None:
    """_parse_jwks logs warning for invalid JSON."""
    import logging
    from orcheo_backend.app.authentication import _parse_jwks

    caplog.set_level(logging.WARNING)

    result = _parse_jwks("not valid json{")

    assert result == []
    assert any("Failed to parse" in record.message for record in caplog.records)


def test_parse_jwks_with_empty_string() -> None:
    """_parse_jwks handles empty string input."""
    from orcheo_backend.app.authentication import _parse_jwks

    result = _parse_jwks("")

    assert result == []


def test_normalize_jwk_list_filters_non_mappings() -> None:
    """_normalize_jwk_list filters out non-mapping entries."""
    from orcheo_backend.app.authentication import _normalize_jwk_list

    mixed_list = [
        {"kty": "RSA", "kid": "key1"},
        "not-a-dict",
        {"kty": "RSA", "kid": "key2"},
        123,
    ]

    result = _normalize_jwk_list(mixed_list)

    assert len(result) == 2
    assert result[0]["kid"] == "key1"
    assert result[1]["kid"] == "key2"


def test_normalize_jwk_list_with_non_sequence() -> None:
    """_normalize_jwk_list returns empty list for non-sequences."""
    from orcheo_backend.app.authentication import _normalize_jwk_list

    assert _normalize_jwk_list("not-a-list") == []
    assert _normalize_jwk_list(123) == []


# Additional tests for missing coverage
