"""Helper tests covering authentication settings parsing utilities."""

from __future__ import annotations
from orcheo_backend.app.authentication.settings import (
    _is_public_hostname,
    _is_public_url,
    _parse_configured_urls,
)


def test_parse_configured_urls_handles_empty_json_and_csv() -> None:
    assert _parse_configured_urls(None) == ()
    assert _parse_configured_urls("   ") == ()

    json_input = '["https://example.com", "  http://other.example/  "]'
    assert _parse_configured_urls(json_input) == (
        "https://example.com",
        "http://other.example/",
    )

    csv_input = "https://foo.example,  https://bar.example  , ,"
    assert _parse_configured_urls(csv_input) == (
        "https://foo.example",
        "https://bar.example",
    )


def test_parse_configured_urls_rejects_non_sequence_types() -> None:
    assert _parse_configured_urls("123") == ()


def test_is_public_url_detects_special_and_public_values() -> None:
    assert not _is_public_url(None)
    assert not _is_public_url("   ")
    assert _is_public_url("*")
    assert not _is_public_url("file:///tmp/foo.toml")
    assert _is_public_url("https://example.com")


def test_is_public_hostname_handles_reserved_and_public_hosts() -> None:
    assert not _is_public_hostname("")
    assert not _is_public_hostname("localhost")
    assert not _is_public_hostname("192.168.1.1")
    assert not _is_public_hostname("example.localdomain")
    assert not _is_public_hostname("internalhost")
    assert _is_public_hostname("example.com")
