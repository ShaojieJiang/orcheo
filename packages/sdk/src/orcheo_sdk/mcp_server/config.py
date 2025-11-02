"""Configuration handling for MCP server."""

from __future__ import annotations
import logging
from functools import lru_cache
from orcheo_sdk.cli.config import CLISettings, resolve_settings
from orcheo_sdk.cli.http import ApiClient


logger = logging.getLogger(__name__)


def get_api_client(
    profile: str | None = None,
    api_url: str | None = None,
    service_token: str | None = None,
) -> tuple[ApiClient, CLISettings]:
    """Get configured API client and settings.

    Args:
        profile: Profile name to use (optional)
        api_url: Override API URL (optional)
        service_token: Override service token (optional)

    Returns:
        Tuple of (ApiClient, CLISettings)

    Raises:
        ValueError: If configuration is invalid or incomplete
    """
    settings = resolve_settings(
        profile=profile,
        api_url=api_url,
        service_token=service_token,
        offline=False,
    )

    if not settings.api_url:
        raise ValueError(
            "ORCHEO_API_URL must be set via environment variable or config file"
        )

    client = ApiClient(
        base_url=settings.api_url,
        token=settings.service_token,
    )

    return client, settings


@lru_cache(maxsize=1)
def validate_server_configuration(
    profile: str | None = None,
    api_url: str | None = None,
    service_token: str | None = None,
) -> CLISettings:
    """Validate configuration for the MCP server at startup."""
    try:
        _, settings = get_api_client(
            profile=profile,
            api_url=api_url,
            service_token=service_token,
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        raise RuntimeError(
            "Failed to initialize Orcheo MCP server configuration."
        ) from exc

    logger.debug(
        "Validated MCP configuration for profile '%s' (api_url=%s)",
        profile or "default",
        settings.api_url,
    )
    return settings
