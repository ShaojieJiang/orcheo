"""Configuration handling for MCP server."""

from orcheo_sdk.cli.config import CLISettings, resolve_settings
from orcheo_sdk.cli.http import ApiClient


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
