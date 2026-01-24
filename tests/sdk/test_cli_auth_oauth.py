"""OAuth flow tests for the CLI."""

from __future__ import annotations
import base64
import hashlib
from orcheo_sdk.cli.auth.oauth import (
    _base64_url_encode,
    _create_code_challenge,
    _create_random_string,
    _parse_jwt_expiry,
)


def test_base64_url_encode_no_padding() -> None:
    # Standard base64 would add padding, base64url should not
    data = b"test"
    result = _base64_url_encode(data)
    assert "=" not in result
    assert result == "dGVzdA"


def test_base64_url_encode_url_safe_chars() -> None:
    # Include bytes that would produce + or / in standard base64
    data = b"\xfb\xff"
    result = _base64_url_encode(data)
    assert "+" not in result
    assert "/" not in result
    # Should use - and _ instead
    assert "-" in result or "_" in result


def test_create_random_string_length() -> None:
    result = _create_random_string(32)
    # Base64 encoding increases length by ~4/3
    assert len(result) >= 32


def test_create_random_string_unique() -> None:
    result1 = _create_random_string(32)
    result2 = _create_random_string(32)
    assert result1 != result2


def test_create_code_challenge_s256() -> None:
    verifier = "test-verifier"
    challenge = _create_code_challenge(verifier)

    # Verify it's the SHA256 of the verifier, base64url encoded
    expected_digest = hashlib.sha256(verifier.encode("ascii")).digest()
    expected = base64.urlsafe_b64encode(expected_digest).rstrip(b"=").decode("ascii")
    assert challenge == expected


def test_parse_jwt_expiry_valid() -> None:
    # Create a minimal JWT with exp claim
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(b'{"exp":1700000000}').rstrip(b"=").decode()
    signature = "signature"
    token = f"{header}.{payload}.{signature}"

    result = _parse_jwt_expiry(token)
    assert result == 1700000000 * 1000  # Converted to milliseconds


def test_parse_jwt_expiry_no_exp() -> None:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(b'{"sub":"user123"}').rstrip(b"=").decode()
    signature = "signature"
    token = f"{header}.{payload}.{signature}"

    result = _parse_jwt_expiry(token)
    assert result is None


def test_parse_jwt_expiry_invalid_token() -> None:
    result = _parse_jwt_expiry("not-a-jwt")
    assert result is None


def test_parse_jwt_expiry_invalid_payload() -> None:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(b"not-json").rstrip(b"=").decode()
    signature = "signature"
    token = f"{header}.{payload}.{signature}"

    result = _parse_jwt_expiry(token)
    assert result is None


def test_parse_jwt_expiry_empty_string() -> None:
    result = _parse_jwt_expiry("")
    assert result is None
