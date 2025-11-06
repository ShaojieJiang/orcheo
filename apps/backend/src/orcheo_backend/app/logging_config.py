"""Centralised logging configuration for the Orcheo backend service."""

from __future__ import annotations
import logging
import os


def configure_logging() -> None:
    """Configure module and framework loggers based on environment variables."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    resolved_level = getattr(logging, log_level, logging.INFO)

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.WARNING,
    )

    for name in (
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "orcheo",
        "orcheo_backend",
    ):
        logging.getLogger(name).setLevel(resolved_level)


configure_logging()


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger instance after ensuring configuration is applied."""
    return logging.getLogger(name or "orcheo_backend.app")


__all__ = ["configure_logging", "get_logger"]
