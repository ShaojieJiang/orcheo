"""Authentication parser tests split from the extended suite."""

from __future__ import annotations
import pytest
from orcheo_backend.app.authentication import AuthenticationError
from tests.backend.authentication_test_utils import reset_auth_state


@pytest.fixture(autouse=True)
def _reset_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure authentication state is cleared between tests."""

    yield from reset_auth_state(monkeypatch)


def test_coerce_str_items_handles_various_types() -> None:
    """_coerce_str_items converts various types to string sets."""
    from orcheo_backend.app.authentication import _coerce_str_items

    # String
    assert _coerce_str_items("item1 item2") == {"item1", "item2"}

    # List
    assert _coerce_str_items(["item1", "item2"]) == {"item1", "item2"}

    # Dict (values only)
    assert _coerce_str_items({"key": "value"}) == {"value"}

    # None
    assert _coerce_str_items(None) == set()


def test_parse_string_items_handles_various_formats() -> None:
    """_parse_string_items parses JSON and space-separated strings."""
    from orcheo_backend.app.authentication import _parse_string_items

    # JSON array
    assert _parse_string_items('["a", "b", "c"]') == ["a", "b", "c"]

    # Space-separated
    assert _parse_string_items("one two three") == ["one", "two", "three"]

    # Empty
    assert _parse_string_items("") == []


def test_coerce_from_string_handles_nested_structures() -> None:
    """_coerce_from_string recursively processes nested structures."""
    from orcheo_backend.app.authentication import _coerce_from_string

    # Nested JSON
    result = _coerce_from_string('["scope1", ["scope2", "scope3"]]')
    assert "scope1" in result
    # Note: nested arrays are processed recursively


def test_coerce_from_mapping_extracts_all_values() -> None:
    """_coerce_from_mapping extracts values from all dict keys."""
    from orcheo_backend.app.authentication import _coerce_from_mapping

    data = {
        "scope1": "read",
        "scope2": "write",
        "list_key": ["admin", "user"],
    }

    result = _coerce_from_mapping(data)

    assert "read" in result
    assert "write" in result
    assert "admin" in result
    assert "user" in result


def test_coerce_from_sequence_processes_all_items() -> None:
    """_coerce_from_sequence processes each sequence item."""
    from orcheo_backend.app.authentication import _coerce_from_sequence

    sequence = ["item1", ["item2", "item3"], "item4"]

    result = _coerce_from_sequence(sequence)

    assert "item1" in result
    assert "item2" in result
    assert "item3" in result
    assert "item4" in result


# Additional tests for missing coverage


def test_coerce_from_string_with_non_list_parsed_json() -> None:
    """_coerce_from_string handles non-list JSON parsing results."""
    from orcheo_backend.app.authentication import _coerce_from_string

    # JSON object string
    result = _coerce_from_string('{"key": "value"}')

    # Should recursively coerce
    assert "value" in result


def test_coerce_str_items_with_non_sequence_mapping() -> None:
    """_coerce_str_items handles mapping types."""
    from orcheo_backend.app.authentication import _coerce_str_items

    result = _coerce_str_items({"key": "value", "key2": ["item1", "item2"]})

    assert "value" in result
    assert "item1" in result


def test_coerce_str_items_with_non_string_value() -> None:
    """_coerce_str_items converts non-string types."""
    from orcheo_backend.app.authentication import _coerce_str_items

    result = _coerce_str_items(12345)

    assert "12345" in result


def test_coerce_str_items_with_empty_after_stripping() -> None:
    """_coerce_str_items returns empty set when value strips to empty."""
    from orcheo_backend.app.authentication import _coerce_str_items

    # String with only whitespace
    result = _coerce_str_items("   ")
    assert result == set()

    # Non-string that converts to empty after strip
    result2 = _coerce_str_items("")
    assert result2 == set()


def test_coerce_from_string_with_empty_strings_in_list() -> None:
    """_coerce_from_string skips empty strings after stripping."""
    from orcheo_backend.app.authentication import _coerce_from_string

    # JSON array with empty/whitespace strings
    result = _coerce_from_string('["token1", "", "  ", "token2"]')

    # Should only include non-empty tokens
    assert "token1" in result
    assert "token2" in result
    assert "" not in result


def test_extract_bearer_token_with_invalid_format() -> None:
    """_extract_bearer_token raises for invalid formats."""
    from orcheo_backend.app.authentication import _extract_bearer_token

    # Missing Bearer prefix
    with pytest.raises(AuthenticationError) as exc:
        _extract_bearer_token("token-value")
    assert exc.value.code == "auth.invalid_scheme"

    # Bearer with only spaces - gets caught by "not 2 parts" check
    with pytest.raises(AuthenticationError) as exc:
        _extract_bearer_token("Bearer")
    assert exc.value.code == "auth.invalid_scheme"

    # None
    with pytest.raises(AuthenticationError) as exc:
        _extract_bearer_token(None)
    assert exc.value.code == "auth.missing_token"


def test_extract_bearer_token_with_valid_format() -> None:
    """_extract_bearer_token successfully extracts valid tokens."""
    from orcheo_backend.app.authentication import _extract_bearer_token

    token = _extract_bearer_token("Bearer my-token-123")
    assert token == "my-token-123"


def test_extract_bearer_token_with_empty_token() -> None:
    """_extract_bearer_token raises for Bearer with empty token."""
    from orcheo_backend.app.authentication import (
        AuthenticationError,
        _extract_bearer_token,
    )

    # "Bearer " with empty token (spaces get stripped)
    with pytest.raises(AuthenticationError) as exc:
        _extract_bearer_token("Bearer ")
    # This is handled by the invalid scheme check since len(parts) != 2
    assert exc.value.code == "auth.invalid_scheme"


def test_extract_bearer_token_with_spaces_after_token() -> None:
    """_extract_bearer_token handles tokens with trailing spaces after strip."""
    from orcheo_backend.app.authentication import _extract_bearer_token

    # Token with spaces after it gets stripped
    token = _extract_bearer_token("Bearer token123   ")
    assert token == "token123"


def test_extract_bearer_token_with_only_whitespace_after_bearer() -> None:
    """_extract_bearer_token raises for Bearer with only whitespace."""
    from orcheo_backend.app.authentication import (
        AuthenticationError,
        _extract_bearer_token,
    )

    # "Bearer" followed by whitespace that strips to empty
    with pytest.raises(AuthenticationError) as exc:
        _extract_bearer_token("Bearer    ")

    assert exc.value.code == "auth.invalid_scheme"
