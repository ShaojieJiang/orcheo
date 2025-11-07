"""Credential encryption primitives and helpers."""

from __future__ import annotations
import hashlib
import os
from base64 import b64decode, b64encode, urlsafe_b64encode
from typing import Protocol
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from orcheo.models.base import OrcheoBaseModel


__all__ = [
    "AesGcmCredentialCipher",
    "CredentialCipher",
    "EncryptionEnvelope",
    "FernetCredentialCipher",
]


class CredentialCipher(Protocol):
    """Protocol describing encryption strategies for credential secrets."""

    algorithm: str
    key_id: str

    def encrypt(self, plaintext: str) -> EncryptionEnvelope:
        """Return an envelope containing ciphertext for the plaintext secret."""
        ...

    def decrypt(self, envelope: EncryptionEnvelope) -> str:
        """Decrypt the provided envelope and return the plaintext secret."""
        ...


class EncryptionEnvelope(OrcheoBaseModel):
    """Encrypted payload metadata produced by a :class:`CredentialCipher`."""

    algorithm: str
    key_id: str
    ciphertext: str

    def decrypt(self, cipher: CredentialCipher) -> str:
        """Use the provided cipher to decrypt the envelope."""
        if cipher.algorithm != self.algorithm:
            msg = "Cipher algorithm mismatch during decryption."
            raise ValueError(msg)
        if cipher.key_id != self.key_id:
            msg = "Cipher key identifier mismatch during decryption."
            raise ValueError(msg)
        return cipher.decrypt(self)


class FernetCredentialCipher:
    """Credential cipher that leverages Fernet symmetric encryption."""

    algorithm: str = "fernet.v1"

    def __init__(self, *, key: str, key_id: str = "primary") -> None:
        """Derive a Fernet key from the provided secret string."""
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        derived_key = urlsafe_b64encode(digest)
        self._fernet = Fernet(derived_key)
        self.key_id = key_id

    def encrypt(self, plaintext: str) -> EncryptionEnvelope:
        """Encrypt plaintext credentials and return an envelope."""
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return EncryptionEnvelope(
            algorithm=self.algorithm,
            key_id=self.key_id,
            ciphertext=token.decode("utf-8"),
        )

    def decrypt(self, envelope: EncryptionEnvelope) -> str:
        """Decrypt an envelope previously produced by :meth:`encrypt`."""
        try:
            plaintext = self._fernet.decrypt(envelope.ciphertext.encode("utf-8"))
        except InvalidToken as exc:  # pragma: no cover - defensive
            msg = "Unable to decrypt credential payload with provided key."
            raise ValueError(msg) from exc
        return plaintext.decode("utf-8")


class AesGcmCredentialCipher:
    """Credential cipher backed by AES-256 GCM."""

    algorithm: str = "aes256-gcm.v1"

    def __init__(self, *, key: str, key_id: str = "primary") -> None:
        """Derive a 256-bit AES key from the provided secret."""
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        self._aesgcm = AESGCM(digest)
        self.key_id = key_id

    def encrypt(self, plaintext: str) -> EncryptionEnvelope:
        """Encrypt plaintext and return an envelope with nonce+ciphertext."""
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        payload = b64encode(nonce + ciphertext).decode("utf-8")
        return EncryptionEnvelope(
            algorithm=self.algorithm,
            key_id=self.key_id,
            ciphertext=payload,
        )

    def decrypt(self, envelope: EncryptionEnvelope) -> str:
        """Decrypt an :class:`EncryptionEnvelope` produced by this cipher."""
        try:
            decoded = b64decode(envelope.ciphertext.encode("utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            msg = "Encrypted payload is not valid base64 data."
            raise ValueError(msg) from exc

        if len(decoded) < 12:
            msg = "Encrypted payload is too short to contain a nonce."
            raise ValueError(msg)

        nonce = decoded[:12]
        ciphertext = decoded[12:]
        try:
            plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)
        except Exception as exc:  # pragma: no cover - defensive
            msg = "Unable to decrypt credential payload with provided key."
            raise ValueError(msg) from exc
        return plaintext.decode("utf-8")
