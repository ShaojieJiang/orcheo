"""CLI command for writing Orcheo CLI profile configuration."""

from __future__ import annotations
import os
import tomllib
from pathlib import Path
from typing import Annotated, Any
import typer
from rich.console import Console
from orcheo_sdk.cli.auth.config import (
    AUTH_AUDIENCE_ENV,
    AUTH_CLIENT_ID_ENV,
    AUTH_ISSUER_ENV,
    AUTH_ORGANIZATION_ENV,
    AUTH_SCOPES_ENV,
)
from orcheo_sdk.cli.config import (
    API_URL_ENV,
    CHATKIT_PUBLIC_BASE_URL_ENV,
    CONFIG_FILENAME,
    DEFAULT_PROFILE,
    PROFILE_ENV,
    SERVICE_TOKEN_ENV,
    get_config_dir,
    load_profiles,
)
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.state import CLIState


config_app = typer.Typer(
    name="config",
    help="Write CLI profile settings to the Orcheo config file.",
)

ProfileOption = Annotated[
    list[str] | None,
    typer.Option(
        "--profile",
        "-p",
        help="Profile name to write (can be provided multiple times).",
    ),
]
EnvFileOption = Annotated[
    Path | None,
    typer.Option("--env-file", help="Path to a .env file to read values from."),
]


def _get_console(ctx: typer.Context) -> Console:
    state: CLIState = ctx.ensure_object(CLIState)
    return state.console


def _read_env_file(env_file: Path) -> dict[str, str]:
    if not env_file.exists():
        raise CLIError(f"Env file not found: {env_file}")

    data: dict[str, str] = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].strip()
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[0] in ("'", '"') and value[-1] == value[0]:
            value = value[1:-1]
        data[key] = value
    return data


def _resolve_value(
    key: str, *, env_data: dict[str, str] | None, override: str | None
) -> str | None:
    if override is not None:
        return override
    if env_data and key in env_data:
        return env_data[key]
    return os.getenv(key)


def _format_toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        inner = ", ".join(_format_toml_value(item) for item in value)
        return f"[{inner}]"
    raise CLIError(f"Unsupported config value type: {type(value).__name__}")


def _resolve_oauth_values(
    *,
    env_data: dict[str, str] | None,
    auth_issuer: str | None,
    auth_client_id: str | None,
    auth_scopes: str | None,
    auth_audience: str | None,
    auth_organization: str | None,
) -> dict[str, str]:
    resolved: dict[str, str] = {}

    resolved_auth_issuer = _resolve_value(
        AUTH_ISSUER_ENV,
        env_data=env_data,
        override=auth_issuer,
    )
    if resolved_auth_issuer:
        resolved[AUTH_ISSUER_ENV] = resolved_auth_issuer

    resolved_auth_client_id = _resolve_value(
        AUTH_CLIENT_ID_ENV,
        env_data=env_data,
        override=auth_client_id,
    )
    if resolved_auth_client_id:
        resolved[AUTH_CLIENT_ID_ENV] = resolved_auth_client_id

    resolved_auth_scopes = _resolve_value(
        AUTH_SCOPES_ENV,
        env_data=env_data,
        override=auth_scopes,
    )
    if resolved_auth_scopes:
        resolved[AUTH_SCOPES_ENV] = resolved_auth_scopes

    resolved_auth_audience = _resolve_value(
        AUTH_AUDIENCE_ENV,
        env_data=env_data,
        override=auth_audience,
    )
    if resolved_auth_audience:
        resolved[AUTH_AUDIENCE_ENV] = resolved_auth_audience

    resolved_auth_organization = _resolve_value(
        AUTH_ORGANIZATION_ENV,
        env_data=env_data,
        override=auth_organization,
    )
    if resolved_auth_organization:
        resolved[AUTH_ORGANIZATION_ENV] = resolved_auth_organization

    return resolved


def _write_profiles(config_path: Path, profiles: dict[str, dict[str, Any]]) -> None:
    lines: list[str] = []
    for profile_name in sorted(profiles):
        profile_data = profiles[profile_name]
        lines.append(f"[profiles.{profile_name}]")
        for key in sorted(profile_data):
            lines.append(f"{key} = {_format_toml_value(profile_data[key])}")
        lines.append("")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines).rstrip() + "\n"
    config_path.write_text(content, encoding="utf-8")


@config_app.callback(invoke_without_command=True)
def configure(
    ctx: typer.Context,
    profile: ProfileOption = None,
    api_url: Annotated[
        str | None,
        typer.Option("--api-url", help="API base URL to write."),
    ] = None,
    service_token: Annotated[
        str | None,
        typer.Option("--service-token", help="Service token to write."),
    ] = None,
    chatkit_public_base_url: Annotated[
        str | None,
        typer.Option(
            "--chatkit-public-base-url",
            help="ChatKit public base URL to write.",
        ),
    ] = None,
    auth_issuer: Annotated[
        str | None,
        typer.Option("--auth-issuer", help="OAuth issuer URL to write."),
    ] = None,
    auth_client_id: Annotated[
        str | None,
        typer.Option("--auth-client-id", help="OAuth client ID to write."),
    ] = None,
    auth_scopes: Annotated[
        str | None,
        typer.Option("--auth-scopes", help="OAuth scopes to write."),
    ] = None,
    auth_audience: Annotated[
        str | None,
        typer.Option("--auth-audience", help="OAuth audience to write."),
    ] = None,
    auth_organization: Annotated[
        str | None,
        typer.Option("--auth-organization", help="OAuth organization to write."),
    ] = None,
    env_file: EnvFileOption = None,
) -> None:
    """Write CLI profile configuration to ``cli.toml``."""
    console = _get_console(ctx)

    env_data = _read_env_file(env_file) if env_file else None
    env_profile = None
    if env_data and PROFILE_ENV in env_data:
        env_profile = env_data[PROFILE_ENV]
    else:
        env_profile = os.getenv(PROFILE_ENV)

    profile_names = profile or [env_profile or DEFAULT_PROFILE]

    resolved_api_url = _resolve_value(API_URL_ENV, env_data=env_data, override=api_url)
    if not resolved_api_url:
        raise CLIError(
            "Missing ORCHEO_API_URL. Provide --api-url or set ORCHEO_API_URL."
        )
    resolved_service_token = _resolve_value(
        SERVICE_TOKEN_ENV,
        env_data=env_data,
        override=service_token,
    )
    resolved_public_base_url = _resolve_value(
        CHATKIT_PUBLIC_BASE_URL_ENV,
        env_data=env_data,
        override=chatkit_public_base_url,
    )
    oauth_values = _resolve_oauth_values(
        env_data=env_data,
        auth_issuer=auth_issuer,
        auth_client_id=auth_client_id,
        auth_scopes=auth_scopes,
        auth_audience=auth_audience,
        auth_organization=auth_organization,
    )

    config_path = get_config_dir() / CONFIG_FILENAME
    try:
        profiles = load_profiles(config_path)
    except tomllib.TOMLDecodeError as exc:
        raise CLIError(f"Invalid TOML in {config_path}.") from exc

    for name in profile_names:
        profile_data = dict(profiles.get(name, {}))
        profile_data["api_url"] = resolved_api_url
        if resolved_service_token:
            profile_data["service_token"] = resolved_service_token
        if resolved_public_base_url:
            profile_data["chatkit_public_base_url"] = resolved_public_base_url
        profile_data.update(oauth_values)
        profiles[name] = profile_data

    _write_profiles(config_path, profiles)
    console.print(
        f"[green]Updated {len(profile_names)} profile(s) in {config_path}.[/green]"
    )
