"""SQLite-backed credential vault implementation."""

from __future__ import annotations
from pathlib import Path
from orcheo.models import CredentialCipher
from orcheo.vault.base import BaseCredentialVault
from orcheo.vault.sqlite_storage import SQLiteCredentialVaultMixin


class FileCredentialVault(SQLiteCredentialVaultMixin, BaseCredentialVault):
    """File-backed credential vault stored in a SQLite database."""

    def __init__(
        self, path: str | Path, *, cipher: CredentialCipher | None = None
    ) -> None:
        """Initialize the SQLite-backed vault."""
        BaseCredentialVault.__init__(self, cipher=cipher)
        SQLiteCredentialVaultMixin.__init__(self, path=path)


__all__ = ["FileCredentialVault"]
