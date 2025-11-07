"""Tests for parsing and constructing credential references."""

from __future__ import annotations
import pytest
from orcheo.runtime.credentials import credential_ref, parse_credential_reference


def test_parse_credential_reference_round_trip() -> None:
    reference = parse_credential_reference("[[telegram_bot]]")
    assert reference is not None
    assert reference.identifier == "telegram_bot"
    assert reference.payload_path == ("secret",)

    oauth_reference = parse_credential_reference("[[telegram_bot#oauth.access_token]]")
    assert oauth_reference is not None
    assert oauth_reference.payload_path == ("oauth", "access_token")

    assert parse_credential_reference("[[  ]]") is None
    assert parse_credential_reference("plain text") is None
    assert parse_credential_reference("[[#oauth]]") is None


def test_credential_ref_helper_accepts_iterable_payload() -> None:
    reference = credential_ref("telegram_bot", ["oauth", "refresh_token"])
    assert reference.payload_path == ("oauth", "refresh_token")


def test_credential_ref_rejects_blank_identifier() -> None:
    with pytest.raises(ValueError):
        credential_ref("   ")


def test_credential_ref_defaults_to_secret_when_payload_blank() -> None:
    reference = credential_ref("telegram_bot", " ")
    assert reference.payload_path == ("secret",)
