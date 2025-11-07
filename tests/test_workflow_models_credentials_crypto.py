"""Credential crypto primitives tests split from the original suite."""

from __future__ import annotations
from base64 import b64encode
import pytest
from orcheo.models import (
    AesGcmCredentialCipher,
    CredentialCipher,
    EncryptionEnvelope,
    FernetCredentialCipher,
)


def test_fernet_cipher_round_trip_and_algorithm_mismatch() -> None:
    cipher = FernetCredentialCipher(key="my-fernet-key", key_id="fernet")

    envelope = cipher.encrypt("top-secret")

    assert envelope.algorithm == cipher.algorithm
    assert envelope.key_id == cipher.key_id
    assert cipher.decrypt(envelope) == "top-secret"
    assert envelope.decrypt(cipher) == "top-secret"

    aes_cipher = AesGcmCredentialCipher(key="another-key", key_id="fernet")
    with pytest.raises(ValueError, match="Cipher algorithm mismatch"):
        envelope.decrypt(aes_cipher)


def test_aes_cipher_rejects_short_payloads() -> None:
    cipher = AesGcmCredentialCipher(key="short-payload-key", key_id="k1")
    bad_payload = b64encode(b"too-short").decode("utf-8")
    envelope = EncryptionEnvelope(
        algorithm=cipher.algorithm,
        key_id=cipher.key_id,
        ciphertext=bad_payload,
    )

    with pytest.raises(ValueError, match="too short"):
        cipher.decrypt(envelope)


def test_credential_cipher_protocol_methods_are_placeholders() -> None:
    """Protocol default implementations should be no-op ellipsis bodies."""
    envelope = EncryptionEnvelope(
        algorithm="test",
        key_id="key1",
        ciphertext="payload",
    )
    encrypt_fn = CredentialCipher.__dict__["encrypt"]
    decrypt_fn = CredentialCipher.__dict__["decrypt"]

    assert encrypt_fn(object(), "secret") is None
    assert decrypt_fn(object(), envelope) is None
