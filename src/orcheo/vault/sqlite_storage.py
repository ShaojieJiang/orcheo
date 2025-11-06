"""Aggregate SQLite-backed persistence mixin for credential vaults."""

from __future__ import annotations
from pathlib import Path
from orcheo.vault.sqlite_alerts import SQLiteAlertStoreMixin
from orcheo.vault.sqlite_core import SQLiteConnectionMixin
from orcheo.vault.sqlite_credentials import SQLiteCredentialStoreMixin
from orcheo.vault.sqlite_templates import SQLiteTemplateStoreMixin


class SQLiteCredentialVaultMixin(
    SQLiteConnectionMixin,
    SQLiteCredentialStoreMixin,
    SQLiteTemplateStoreMixin,
    SQLiteAlertStoreMixin,
):
    """Composite mixin that wires together SQLite storage helpers."""

    def __init__(self, path: str | Path) -> None:
        """Initialize the composite mixin with the SQLite database path."""
        SQLiteConnectionMixin.__init__(self, path=path)


__all__ = ["SQLiteCredentialVaultMixin"]
