"""Manifest persistence and provider-local locking helpers."""

from __future__ import annotations
import fcntl
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from orcheo.external_agents.models import (
    ProviderLockUnavailableError,
    RuntimeManifest,
)
from orcheo.external_agents.paths import (
    provider_lock_path,
    provider_manifest_path,
    provider_root,
)


@contextmanager
def provider_lock(
    runtime_root: Path,
    provider: str,
    *,
    blocking: bool = True,
) -> Iterator[None]:
    """Acquire an advisory provider-local filesystem lock."""
    lock_path = provider_lock_path(runtime_root, provider)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+", encoding="utf-8") as handle:
        lock_flags = fcntl.LOCK_EX
        if not blocking:
            lock_flags |= fcntl.LOCK_NB
        try:
            fcntl.flock(handle.fileno(), lock_flags)
        except BlockingIOError as exc:  # pragma: no cover - platform-level timing
            msg = f"Provider lock for '{provider}' is already held."
            raise ProviderLockUnavailableError(msg) from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class RuntimeManifestStore:
    """Filesystem-backed manifest store for external agent runtimes."""

    def __init__(self, runtime_root: Path) -> None:
        """Initialize the manifest store for one managed runtime root."""
        self.runtime_root = runtime_root

    def load(self, provider: str) -> RuntimeManifest | None:
        """Load the manifest for ``provider`` if present."""
        manifest_path = provider_manifest_path(self.runtime_root, provider)
        if not manifest_path.exists():
            return None
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        return RuntimeManifest.model_validate(payload)

    def save(self, manifest: RuntimeManifest) -> RuntimeManifest:
        """Persist ``manifest`` atomically."""
        provider_dir = provider_root(self.runtime_root, manifest.provider)
        provider_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = provider_manifest_path(self.runtime_root, manifest.provider)

        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=provider_dir,
            delete=False,
        ) as handle:
            json.dump(
                manifest.model_dump(mode="json"), handle, indent=2, sort_keys=True
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)

        os.replace(temp_path, manifest_path)
        return manifest
