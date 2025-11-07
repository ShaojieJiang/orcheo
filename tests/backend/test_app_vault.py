"""Tests covering vault creation and key management helpers."""

from __future__ import annotations
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
from orcheo.vault import FileCredentialVault
from orcheo_backend.app import _create_vault, _ensure_file_vault_key


def test_create_vault_supports_file_backend(tmp_path: Path) -> None:
    """File-backed vaults expand the configured path and return an instance."""

    path = tmp_path / "orcheo" / "vault.sqlite"
    settings = SimpleNamespace(
        vault=SimpleNamespace(
            backend="file",
            local_path=str(path),
            encryption_key="unit-test-key",
        )
    )

    vault = _create_vault(settings)  # type: ignore[arg-type]

    assert isinstance(vault, FileCredentialVault)
    assert vault._path == path.expanduser()  # type: ignore[attr-defined]


def test_create_vault_generates_encryption_key(tmp_path: Path) -> None:
    """Missing encryption keys are generated and stored alongside the database."""

    path = tmp_path / "vault.sqlite"
    settings = SimpleNamespace(
        vault=SimpleNamespace(
            backend="file",
            local_path=str(path),
            encryption_key=None,
        )
    )

    vault = _create_vault(settings)  # type: ignore[arg-type]

    assert isinstance(vault, FileCredentialVault)
    key_path = path.with_name(f"{path.stem}.key")
    assert key_path.exists()
    key_contents = key_path.read_text(encoding="utf-8").strip()
    assert len(key_contents) == 64

    _create_vault(settings)  # type: ignore[arg-type]

    assert key_path.read_text(encoding="utf-8").strip() == key_contents


def test_ensure_file_vault_key_returns_existing_value(tmp_path: Path) -> None:
    path = tmp_path / "vault.sqlite"
    key_path = path.with_name(f"{path.stem}.key")
    key_path.write_text(" existing-key ", encoding="utf-8")

    key = _ensure_file_vault_key(path, None)

    assert key == "existing-key"
    assert key_path.read_text(encoding="utf-8") == " existing-key "


def test_ensure_file_vault_key_regenerates_when_existing_blank(tmp_path: Path) -> None:
    path = tmp_path / "vault.sqlite"
    key_path = path.with_name(f"{path.stem}.key")
    key_path.write_text("   \n", encoding="utf-8")

    key = _ensure_file_vault_key(path, None)

    assert len(key) == 64
    assert key_path.read_text(encoding="utf-8").strip() == key


def test_ensure_file_vault_key_handles_chmod_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "vault.sqlite"
    calls: list[tuple[Path, int]] = []

    def raise_permission_error(target: Path, mode: int) -> None:
        calls.append((target, mode))
        raise PermissionError("chmod not permitted")

    monkeypatch.setattr(os, "chmod", raise_permission_error)

    key = _ensure_file_vault_key(path, None)

    key_path = path.with_name(f"{path.stem}.key")
    assert key_path.exists()
    assert len(key) == 64
    assert calls and calls[0][0] == key_path


def test_create_vault_rejects_unsupported_backend() -> None:
    """Unsupported vault backends raise a clear error message."""

    settings = SimpleNamespace(vault=SimpleNamespace(backend="aws_kms"))

    with pytest.raises(ValueError, match="not supported"):
        _create_vault(settings)  # type: ignore[arg-type]
