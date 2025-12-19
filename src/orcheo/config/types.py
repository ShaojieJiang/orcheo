"""Type aliases for Orcheo configuration."""

from typing import Literal


CheckpointBackend = Literal["sqlite", "postgres"]
RepositoryBackend = Literal["inmemory", "sqlite", "postgres"]
VaultBackend = Literal["inmemory", "file", "aws_kms"]

__all__ = ["CheckpointBackend", "RepositoryBackend", "VaultBackend"]
