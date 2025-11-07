"""Default values shared across configuration models."""

_DEFAULTS: dict[str, object] = {
    "CHECKPOINT_BACKEND": "sqlite",
    "SQLITE_PATH": "~/.orcheo/checkpoints.sqlite",
    "REPOSITORY_BACKEND": "sqlite",
    "REPOSITORY_SQLITE_PATH": "~/.orcheo/workflows.sqlite",
    "CHATKIT_SQLITE_PATH": "~/.orcheo/chatkit.sqlite",
    "CHATKIT_STORAGE_PATH": "~/.orcheo/chatkit",
    "CHATKIT_RETENTION_DAYS": 30,
    "POSTGRES_DSN": None,
    "HOST": "0.0.0.0",
    "PORT": 8000,
    "VAULT_BACKEND": "file",
    "VAULT_ENCRYPTION_KEY": None,
    "VAULT_LOCAL_PATH": "~/.orcheo/vault.sqlite",
    "VAULT_AWS_REGION": None,
    "VAULT_AWS_KMS_KEY_ID": None,
    "VAULT_TOKEN_TTL_SECONDS": 3600,
}

__all__ = ["_DEFAULTS"]
