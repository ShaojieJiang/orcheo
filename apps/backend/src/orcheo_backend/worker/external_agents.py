"""Worker-side helpers for external agent status checks and OAuth sessions."""

from __future__ import annotations
import os
import pty
import re
import selectors
import signal
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from orcheo.external_agents import ExternalAgentRuntimeManager, RuntimeInstallError
from orcheo.external_agents.models import ResolvedRuntime
from orcheo_backend.app.dependencies import get_external_agent_runtime_store
from orcheo_backend.app.external_agent_runtime_store import (
    default_external_agent_status,
)
from orcheo_backend.app.schemas.system import (
    ExternalAgentLoginSession,
    ExternalAgentLoginSessionState,
    ExternalAgentProviderName,
    ExternalAgentProviderState,
    ExternalAgentProviderStatus,
)


LOGIN_TIMEOUT_SECONDS = 15 * 60
MAX_RECENT_OUTPUT_CHARS = 4000
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
URL_PATTERN = re.compile(r"https?://[^\s]+")
DEVICE_CODE_PATTERN = re.compile(r"\b[A-Z0-9]{4}(?:-[A-Z0-9]{4,})+\b")


@dataclass(slots=True)
class LoginCommandResult:
    """Captured result from a worker-side interactive login command."""

    exit_code: int | None
    timed_out: bool
    output: str
    auth_url: str | None
    device_code: str | None


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _trim_recent_output(output: str) -> str:
    return output[-MAX_RECENT_OUTPUT_CHARS:]


def _strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_PATTERN.sub("", text)


def _extract_auth_url(output: str) -> str | None:
    matches = URL_PATTERN.findall(output)
    if not matches:
        return None
    for candidate in matches:
        if "localhost" not in candidate and "127.0.0.1" not in candidate:
            return candidate
    return matches[0]


def _extract_device_code(output: str) -> str | None:
    match = DEVICE_CODE_PATTERN.search(output)
    return match.group(0) if match is not None else None


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        process.wait(timeout=2)


def _drain_login_output(
    master_fd: int,
    *,
    output: str,
    auth_url: str | None,
    device_code: str | None,
    on_output: Callable[[str, str | None, str | None], None],
) -> tuple[str, str | None, str | None]:
    """Read and normalize any available PTY output for the login process."""
    while True:
        try:
            chunk = os.read(master_fd, 4096)
        except BlockingIOError:
            break
        except OSError:
            chunk = b""
        if not chunk:
            break
        cleaned = _strip_ansi(chunk.decode("utf-8", errors="replace"))
        output += cleaned
        auth_url = auth_url or _extract_auth_url(output)
        device_code = device_code or _extract_device_code(output)
        on_output(output, auth_url, device_code)
    return output, auth_url, device_code


def _forward_login_input(
    master_fd: int,
    consume_input: Callable[[], str | None] | None,
) -> None:
    """Send any queued operator input back to the interactive login PTY."""
    if consume_input is None:
        return
    queued_input = consume_input()
    if queued_input:
        os.write(master_fd, f"{queued_input}\n".encode())


def _run_login_command(
    command: list[str],
    *,
    env: Mapping[str, str],
    on_output: Callable[[str, str | None, str | None], None],
    consume_input: Callable[[], str | None] | None = None,
    timeout_seconds: int = LOGIN_TIMEOUT_SECONDS,
) -> LoginCommandResult:
    """Run an interactive provider login command inside a PTY."""
    master_fd, slave_fd = pty.openpty()
    os.set_blocking(master_fd, False)
    selector = selectors.DefaultSelector()
    process: subprocess.Popen[bytes] | None = None
    output = ""
    auth_url: str | None = None
    device_code: str | None = None
    timed_out = False
    try:
        process = subprocess.Popen(
            command,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=dict(env),
            start_new_session=True,
            close_fds=True,
        )
        selector.register(master_fd, selectors.EVENT_READ)
        started_at = time.monotonic()

        while True:
            selector.select(timeout=0.5)
            output, auth_url, device_code = _drain_login_output(
                master_fd,
                output=output,
                auth_url=auth_url,
                device_code=device_code,
                on_output=on_output,
            )
            _forward_login_input(master_fd, consume_input)

            if process.poll() is not None:
                break
            if time.monotonic() - started_at > timeout_seconds:
                timed_out = True
                _terminate_process_group(process)
                break

        exit_code = process.wait(timeout=2)
        return LoginCommandResult(
            exit_code=exit_code,
            timed_out=timed_out,
            output=output,
            auth_url=auth_url,
            device_code=device_code,
        )
    finally:
        selector.close()
        os.close(master_fd)
        os.close(slave_fd)
        if process is not None and process.poll() is None:
            _terminate_process_group(process)


def _provider_status(
    provider_name: ExternalAgentProviderName,
    *,
    state: ExternalAgentProviderState,
    authenticated: bool,
    installed: bool,
    detail: str | None,
    resolved_version: str | None = None,
    executable_path: str | None = None,
    checked_at: datetime | None = None,
    last_auth_ok_at: datetime | None = None,
    active_session_id: str | None = None,
) -> ExternalAgentProviderStatus:
    """Build a provider status payload from the current worker state."""
    base = default_external_agent_status(provider_name)
    return base.model_copy(
        update={
            "state": state,
            "authenticated": authenticated,
            "installed": installed,
            "detail": detail,
            "resolved_version": resolved_version,
            "executable_path": executable_path,
            "checked_at": checked_at,
            "last_auth_ok_at": last_auth_ok_at,
            "active_session_id": active_session_id,
        }
    )


def _initial_login_detail(provider_name: ExternalAgentProviderName) -> str:
    """Return the initial operator guidance for a provider login session."""
    if provider_name == ExternalAgentProviderName.CODEX:
        return (
            "Complete the Codex device-auth flow. If ChatGPT says device code "
            "authorization is disabled, enable it in ChatGPT Security Settings and "
            "retry."
        )
    return "Starting the provider OAuth flow on the worker."


def _browser_login_detail(provider_name: ExternalAgentProviderName) -> str:
    """Return provider-specific guidance while a browser login is in progress."""
    if provider_name == ExternalAgentProviderName.CODEX:
        return (
            "Open the device-auth page, enter the one-time device code, and finish "
            "sign-in. If ChatGPT says device authorization is disabled, enable it "
            "in ChatGPT Security Settings and retry."
        )
    if provider_name == ExternalAgentProviderName.CLAUDE_CODE:
        return (
            "Complete the browser sign-in. If Claude shows a one-time code at the "
            "end, paste it back into Canvas to finish worker auth."
        )
    return "Complete the browser sign-in to finish connecting the worker."


def _last_auth_ok_at(manifest: object | None) -> datetime | None:
    """Return the stored last-auth timestamp when a manifest is present."""
    return getattr(manifest, "last_auth_ok_at", None)


def _save_ready_provider_status(
    runtime_store: object,
    provider_id: ExternalAgentProviderName,
    *,
    runtime_version: str,
    executable_path: str,
    checked_at: datetime,
    last_auth_ok_at: datetime | None,
) -> None:
    """Persist a ready/authenticated provider status."""
    runtime_store.save_provider_status(  # type: ignore[attr-defined]
        _provider_status(
            provider_id,
            state=ExternalAgentProviderState.READY,
            authenticated=True,
            installed=True,
            detail="Ready on the worker.",
            resolved_version=runtime_version,
            executable_path=executable_path,
            checked_at=checked_at,
            last_auth_ok_at=last_auth_ok_at,
        )
    )


def _save_needs_login_provider_status(
    runtime_store: object,
    provider_id: ExternalAgentProviderName,
    *,
    detail: str,
    runtime_version: str,
    executable_path: str,
    checked_at: datetime,
    last_auth_ok_at: datetime | None,
) -> None:
    """Persist a worker status showing provider login is still required."""
    runtime_store.save_provider_status(  # type: ignore[attr-defined]
        _provider_status(
            provider_id,
            state=ExternalAgentProviderState.NEEDS_LOGIN,
            authenticated=False,
            installed=True,
            detail=detail,
            resolved_version=runtime_version,
            executable_path=executable_path,
            checked_at=checked_at,
            last_auth_ok_at=last_auth_ok_at,
        )
    )


async def refresh_external_agent_status_async(provider_name: str) -> dict[str, str]:
    """Refresh one provider status without forcing a runtime install."""
    provider_id = ExternalAgentProviderName(provider_name)
    runtime_store = get_external_agent_runtime_store()
    manager = ExternalAgentRuntimeManager()
    provider = manager.get_provider(provider_name)
    checked_at = _utcnow()

    try:
        runtime, manifest = manager.inspect_runtime(provider_name)
        if runtime is None:
            runtime_store.save_provider_status(
                _provider_status(
                    provider_id,
                    state=ExternalAgentProviderState.NOT_INSTALLED,
                    authenticated=False,
                    installed=False,
                    detail="Runtime not installed on the worker yet.",
                    checked_at=checked_at,
                )
            )
            return {"status": "not_installed"}

        probe = provider.probe_auth(runtime, environ=manager.environ)
        if probe.authenticated:
            manifest = manager.mark_auth_success(provider_name)
            _save_ready_provider_status(
                runtime_store,
                provider_id,
                runtime_version=runtime.version,
                executable_path=str(runtime.executable_path),
                checked_at=checked_at,
                last_auth_ok_at=manifest.last_auth_ok_at,
            )
            return {"status": "ready"}

        _save_needs_login_provider_status(
            runtime_store,
            provider_id,
            detail=probe.message or "OAuth login is required on the worker.",
            runtime_version=runtime.version,
            executable_path=str(runtime.executable_path),
            checked_at=checked_at,
            last_auth_ok_at=_last_auth_ok_at(manifest),
        )
        return {"status": "needs_login"}
    except Exception as exc:
        runtime_store.save_provider_status(
            _provider_status(
                provider_id,
                state=ExternalAgentProviderState.ERROR,
                authenticated=False,
                installed=False,
                detail=str(exc),
                checked_at=checked_at,
            )
        )
        return {"status": "error", "detail": str(exc)}


async def start_external_agent_login_async(  # noqa: C901, PLR0915
    provider_name: str,
    session_id: str,
) -> dict[str, str]:
    """Install the provider runtime if needed and run the interactive OAuth flow."""
    provider_id = ExternalAgentProviderName(provider_name)
    runtime_store = get_external_agent_runtime_store()
    manager = ExternalAgentRuntimeManager()
    provider = manager.get_provider(provider_name)
    session = runtime_store.get_login_session(session_id)
    if session is None:
        return {"status": "missing_session"}

    def save_session(
        state: ExternalAgentLoginSessionState,
        *,
        detail: str | None,
        auth_url: str | None = None,
        device_code: str | None = None,
        recent_output: str | None = None,
        resolved_version: str | None = None,
        executable_path: str | None = None,
        completed: bool = False,
    ) -> ExternalAgentLoginSession:
        current = runtime_store.get_login_session(session_id) or session
        updated = current.model_copy(
            update={
                "state": state,
                "detail": detail,
                "auth_url": auth_url,
                "device_code": device_code,
                "recent_output": recent_output,
                "resolved_version": resolved_version,
                "executable_path": executable_path,
                "updated_at": _utcnow(),
                "completed_at": _utcnow() if completed else None,
            }
        )
        runtime_store.save_login_session(updated)
        return updated

    def save_authenticated_session(
        current_runtime: ResolvedRuntime,
        detail: str,
    ) -> None:
        """Persist a completed authenticated worker login session."""
        save_session(
            ExternalAgentLoginSessionState.AUTHENTICATED,
            detail=detail,
            resolved_version=current_runtime.version,
            executable_path=str(current_runtime.executable_path),
            completed=True,
        )

    def save_provider_ready(
        current_runtime: ResolvedRuntime,
        manifest_last_auth_ok_at: datetime | None,
    ) -> None:
        """Persist a ready provider state for the current runtime."""
        _save_ready_provider_status(
            runtime_store,
            provider_id,
            runtime_version=current_runtime.version,
            executable_path=str(current_runtime.executable_path),
            checked_at=_utcnow(),
            last_auth_ok_at=manifest_last_auth_ok_at,
        )

    try:
        runtime, manifest = manager.inspect_runtime(provider_name)
        if runtime is None:
            save_session(
                ExternalAgentLoginSessionState.INSTALLING,
                detail="Installing the managed runtime on the worker.",
            )
            runtime_store.save_provider_status(
                _provider_status(
                    provider_id,
                    state=ExternalAgentProviderState.INSTALLING,
                    authenticated=False,
                    installed=False,
                    detail="Installing the managed runtime on the worker.",
                    active_session_id=session_id,
                    checked_at=_utcnow(),
                )
            )
            resolution = await manager.resolve_runtime(provider_name)
            runtime = resolution.runtime
            manifest = resolution.manifest

        probe = provider.probe_auth(runtime, environ=manager.environ)
        if probe.authenticated:
            manifest = manager.mark_auth_success(provider_name)
            save_authenticated_session(runtime, "Already authenticated on the worker.")
            save_provider_ready(runtime, manifest.last_auth_ok_at)
            return {"status": "ready"}

        save_session(
            ExternalAgentLoginSessionState.PENDING,
            detail=_initial_login_detail(provider_id),
            resolved_version=runtime.version,
            executable_path=str(runtime.executable_path),
        )
        runtime_store.save_provider_status(
            _provider_status(
                provider_id,
                state=ExternalAgentProviderState.AUTHENTICATING,
                authenticated=False,
                installed=True,
                detail="Waiting for browser-based sign-in.",
                resolved_version=runtime.version,
                executable_path=str(runtime.executable_path),
                checked_at=_utcnow(),
                last_auth_ok_at=manifest.last_auth_ok_at
                if manifest is not None
                else None,
                active_session_id=session_id,
            )
        )

        def on_output(
            output: str,
            auth_url: str | None,
            device_code: str | None,
        ) -> None:
            detail = _browser_login_detail(provider_id)
            state = (
                ExternalAgentLoginSessionState.AWAITING_OAUTH
                if auth_url or device_code
                else ExternalAgentLoginSessionState.PENDING
            )
            save_session(
                state,
                detail=detail,
                auth_url=auth_url,
                device_code=device_code,
                recent_output=_trim_recent_output(output),
                resolved_version=runtime.version,
                executable_path=str(runtime.executable_path),
            )

        result = _run_login_command(
            provider.oauth_login_command(runtime),
            env=provider.build_environment(manager.environ),
            on_output=on_output,
            consume_input=lambda: runtime_store.consume_login_input(session_id),
        )
        probe = provider.probe_auth(runtime, environ=manager.environ)
        if probe.authenticated:
            manifest = manager.mark_auth_success(provider_name)
            save_session(
                ExternalAgentLoginSessionState.AUTHENTICATED,
                detail="Worker authentication completed successfully.",
                auth_url=result.auth_url,
                device_code=result.device_code,
                recent_output=_trim_recent_output(result.output),
                resolved_version=runtime.version,
                executable_path=str(runtime.executable_path),
                completed=True,
            )
            save_provider_ready(runtime, manifest.last_auth_ok_at)
            return {"status": "authenticated"}

        session_state = (
            ExternalAgentLoginSessionState.TIMED_OUT
            if result.timed_out
            else ExternalAgentLoginSessionState.FAILED
        )
        detail = (
            "The login session timed out before the worker was authenticated."
            if result.timed_out
            else "The OAuth flow exited before authentication completed."
        )
        save_session(
            session_state,
            detail=detail,
            auth_url=result.auth_url,
            device_code=result.device_code,
            recent_output=_trim_recent_output(result.output),
            resolved_version=runtime.version,
            executable_path=str(runtime.executable_path),
            completed=True,
        )
        _save_needs_login_provider_status(
            runtime_store,
            provider_id,
            detail=detail,
            runtime_version=runtime.version,
            executable_path=str(runtime.executable_path),
            checked_at=_utcnow(),
            last_auth_ok_at=_last_auth_ok_at(manifest),
        )
        return {"status": session_state.value}
    except RuntimeInstallError as exc:
        save_session(
            ExternalAgentLoginSessionState.FAILED,
            detail=f"Failed to install the managed runtime: {exc}",
            completed=True,
        )
        runtime_store.save_provider_status(
            _provider_status(
                provider_id,
                state=ExternalAgentProviderState.ERROR,
                authenticated=False,
                installed=False,
                detail=f"Failed to install the managed runtime: {exc}",
                checked_at=_utcnow(),
            )
        )
        return {"status": "install_failed"}
    except Exception as exc:
        save_session(
            ExternalAgentLoginSessionState.FAILED,
            detail=str(exc),
            completed=True,
        )
        runtime_store.save_provider_status(
            _provider_status(
                provider_id,
                state=ExternalAgentProviderState.ERROR,
                authenticated=False,
                installed=False,
                detail=str(exc),
                checked_at=_utcnow(),
            )
        )
        return {"status": "error", "detail": str(exc)}


__all__ = [
    "refresh_external_agent_status_async",
    "start_external_agent_login_async",
]
