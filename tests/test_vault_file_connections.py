"""Connection pool tests for FileCredentialVault."""

from __future__ import annotations
import sqlite3
from pathlib import Path
import pytest
from orcheo.vault import FileCredentialVault


def test_file_vault_acquire_connection_creates_when_pool_empty(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault.sqlite"
    vault = FileCredentialVault(vault_path)

    while not vault._connection_pool.empty():
        connection = vault._connection_pool.get_nowait()
        connection.close()

    with vault._acquire_connection() as connection:
        assert connection.execute("PRAGMA user_version").fetchone() is not None

    while not vault._connection_pool.empty():
        connection = vault._connection_pool.get_nowait()
        connection.close()


def test_file_vault_release_connection_rolls_back_and_limits_pool(
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "vault.sqlite"
    vault = FileCredentialVault(vault_path)

    while not vault._connection_pool.empty():
        connection = vault._connection_pool.get_nowait()
        connection.close()

    for _ in range(vault._connection_pool.maxsize):
        vault._connection_pool.put_nowait(vault._create_connection())

    extra_connection = vault._create_connection()
    extra_connection.execute("BEGIN")
    vault._release_connection(extra_connection)

    assert vault._connection_pool.qsize() == vault._connection_pool.maxsize
    with pytest.raises(sqlite3.ProgrammingError):
        extra_connection.execute("SELECT 1")

    while not vault._connection_pool.empty():
        connection = vault._connection_pool.get_nowait()
        connection.close()
