"""Tests for worker-side external agent login helpers."""

from __future__ import annotations
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from orcheo_backend.app.external_agent_runtime_store import ExternalAgentRuntimeStore
from orcheo_backend.app.schemas.system import (
    ExternalAgentLoginSession,
    ExternalAgentLoginSessionState,
    ExternalAgentProviderName,
    ExternalAgentProviderState,
    ExternalAgentProviderStatus,
)
from orcheo_backend.worker.external_agents import _extract_auth_url


def test_extract_auth_url_prefers_public_url_over_localhost() -> None:
    """Public auth links should win over worker-local callback URLs."""
    output = """
Starting local login server on http://localhost:1455.
If your browser did not open, navigate to this URL to authenticate:
https://auth.openai.com/oauth/authorize?response_type=code
"""

    assert (
        _extract_auth_url(output)
        == "https://auth.openai.com/oauth/authorize?response_type=code"
    )


def test_extract_auth_url_stops_before_next_prompt_line() -> None:
    """Wrapped URLs should not absorb the next terminal prompt line."""
    output = """
Browser didn't open? Use the url below to signin

https://claude.com/cai/oauth/authorize?code=true&client_id=abc123&response_type=code
&redirect_uri=https%3A%2F%2Fplatform.claude.com%2Foauth%2Fcode%2Fcallback
Pastecodehereifprompted>
"""

    assert _extract_auth_url(output) == (
        "https://claude.com/cai/oauth/authorize?code=true&client_id=abc123"
        "&response_type=code&redirect_uri=https%3A%2F%2Fplatform.claude.com"
        "%2Foauth%2Fcode%2Fcallback"
    )


def test_extract_auth_url_skips_one_blank_wrapped_line() -> None:
    """Claude's wrapped OAuth URL should survive one blank spacer line."""
    output = """
https://claude.com/cai/oauth/authorize?code=true&client_id=9d1c250a-e61b-44d9-88ed-5944d1962f5e&response_type=code&redirect_uri=https%3A%2F%2Fplatform.claude.com%2Foauth%2Fcode%2Fcallback&scope=user%3Ainference&code_challenge=1G_Pjb3eDvtNbl

jeSRFodV_IfJ_ooj5nfszVier81_w&code_challenge_method=S256&state=bjdD4VJiqv6dlffcqzUmdj9bUUu_eHTAASug9n8lhbg
"""

    assert _extract_auth_url(output) == (
        "https://claude.com/cai/oauth/authorize?code=true&client_id="
        "9d1c250a-e61b-44d9-88ed-5944d1962f5e&response_type=code&redirect_uri="
        "https%3A%2F%2Fplatform.claude.com%2Foauth%2Fcode%2Fcallback&scope="
        "user%3Ainference&code_challenge=1G_Pjb3eDvtNbl"
        "jeSRFodV_IfJ_ooj5nfszVier81_w&code_challenge_method=S256&state="
        "bjdD4VJiqv6dlffcqzUmdj9bUUu_eHTAASug9n8lhbg"
    )


def test_runtime_store_persists_provider_environment() -> None:
    """Shared runtime store should round-trip provider env vars."""
    store = ExternalAgentRuntimeStore()
    store._redis = None

    store.save_provider_environment(
        ExternalAgentProviderName.CLAUDE_CODE,
        {"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-shared"},
    )

    assert store.get_provider_environment(ExternalAgentProviderName.CLAUDE_CODE) == {
        "CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-shared"
    }


def test_run_login_command_finishes_when_auth_becomes_valid() -> None:
    """Interactive login should complete once auth succeeds, even silently."""
    from orcheo_backend.worker.external_agents import _run_login_command

    def on_output(_: str, __: str | None, ___: str | None) -> None:
        return None

    checks = 0

    def is_authenticated() -> bool:
        nonlocal checks
        checks += 1
        return checks >= 2

    started_at = time.monotonic()
    result = _run_login_command(
        [
            "python3",
            "-c",
            (
                "import time; "
                "print('Opening browser to sign in...', flush=True); "
                "time.sleep(30)"
            ),
        ],
        env={},
        on_output=on_output,
        is_authenticated=is_authenticated,
        timeout_seconds=10,
    )

    assert "Opening browser to sign in..." in result.output
    assert result.timed_out is False
    assert time.monotonic() - started_at < 10


def test_run_login_command_redacts_oauth_token_output() -> None:
    """Worker session output should redact minted Claude OAuth tokens."""
    from orcheo_backend.worker.external_agents import _run_login_command

    def on_output(_: str, __: str | None, ___: str | None) -> None:
        return None

    result = _run_login_command(
        [
            "python3",
            "-c",
            (
                "print('Your OAuth token (valid for 1 year):', flush=True); "
                "print('sk-ant-oat01-secret-token', flush=True); "
                "print('Store this token securely.', flush=True)"
            ),
        ],
        env={},
        on_output=on_output,
        timeout_seconds=10,
    )

    assert result.auth_token == "sk-ant-oat01-secret-token"
    assert "sk-ant-oat01-secret-token" not in result.output
    assert "[redacted worker auth token]" in result.output


def test_run_login_command_extracts_wrapped_token_before_process_exit() -> None:
    """Final Claude token output should be captured even if the process exits fast."""
    from orcheo_backend.worker.external_agents import _run_login_command

    script = (
        "import os, sys, termios, tty\n"
        "fd = sys.stdin.fileno()\n"
        "old = termios.tcgetattr(fd)\n"
        "tty.setraw(fd)\n"
        "sys.stdout.write('Paste code here if prompted> ')\n"
        "sys.stdout.flush()\n"
        "try:\n"
        "    while True:\n"
        "        ch = os.read(fd, 1)\n"
        "        if ch == b'\\r':\n"
        "            break\n"
        "finally:\n"
        "    termios.tcsetattr(fd, termios.TCSADRAIN, old)\n"
        "print('\\nYour OAuth token (valid for 1 year):\\n', flush=True)\n"
        "print('sk-ant-oat01-verylongtokenpartone', flush=True)\n"
        "print('parttwo', flush=True)\n"
        "print('\\nStore this token securely. "
        "You won\\'t be able to see it again.', flush=True)\n"
    )
    queued = {"value": "ABCD-1234"}

    def on_output(_: str, __: str | None, ___: str | None) -> None:
        return None

    def consume_input(clear: bool) -> str | None:
        if clear:
            queued["value"] = None
            return None
        return queued["value"]

    result = _run_login_command(
        ["python3", "-c", script],
        env={},
        on_output=on_output,
        consume_input=consume_input,
        timeout_seconds=10,
    )

    assert result.auth_token == "sk-ant-oat01-verylongtokenpartoneparttwo"
    assert "sk-ant-oat01-verylongtokenpartone" not in result.output
    assert "[redacted worker auth token]" in result.output


def test_run_login_command_uses_visible_terminal_screen_for_rewritten_token() -> None:
    """Token extraction should keep the latest rewritten token within one block."""
    from orcheo_backend.worker.external_agents import _run_login_command

    script = (
        "import sys\n"
        "sys.stdout.write('Your OAuth token (valid for 1 year):\\n')\n"
        "sys.stdout.write('sk-ant-oat01-stale-token')\n"
        "sys.stdout.flush()\n"
        "sys.stdout.write('\\r')\n"
        "sys.stdout.write('sk-ant-oat01-fresh-token')\n"
        "sys.stdout.write('\\nStore this token securely.\\n')\n"
        "sys.stdout.flush()\n"
    )

    def on_output(_: str, __: str | None, ___: str | None) -> None:
        return None

    result = _run_login_command(
        ["python3", "-c", script],
        env={},
        on_output=on_output,
        timeout_seconds=10,
    )

    assert result.auth_token == "sk-ant-oat01-fresh-token"
    assert "sk-ant-oat01-stale-token" not in result.output
    assert "[redacted worker auth token]" in result.output


def test_extract_visible_auth_token_rejects_masked_claude_token_block() -> None:
    """Rendered screen output should not mint fake tokens from masked lines."""
    from orcheo_backend.worker.external_agents import _extract_visible_auth_token

    output = (
        "Your OAuth token (valid for 1 year):\n"
        "sk-ant-oat01-AAAA*********JFZmvs\n"
        "Store this token securely.\n"
    )

    assert _extract_visible_auth_token(output) is None


def test_extract_worker_auth_token_prefers_raw_unmasked_token() -> None:
    """Raw PTY output should win when the rendered screen shows a masked token."""
    from orcheo_backend.worker.external_agents import _extract_worker_auth_token

    raw_output = (
        "Your OAuth token (valid for 1 year):\n"
        "sk-ant-oat01-AAAABBBBCCCCDDDDEEEE\n"
        "FFFFGGGGHHHHIIIIJJJJ\n"
        "Store this token securely.\n"
    )
    visible_output = (
        "Your OAuth token (valid for 1 year):\n"
        "sk-ant-oat01-AAAABBBB*********JFZmvs\n"
        "Store this token securely.\n"
    )

    assert _extract_worker_auth_token(raw_output, visible_output) == (
        "sk-ant-oat01-AAAABBBBCCCCDDDDEEEEFFFFGGGGHHHHIIIIJJJJ"
    )


def test_run_login_command_extracts_token_from_compacted_claude_output() -> None:
    """Claude PTY output can collapse spaces; token extraction should still work."""
    from orcheo_backend.worker.external_agents import _extract_auth_token

    output = (
        "Long-livedauthenticationtokencreatedsuccessfully!\n"
        "Your OAuth tokn (valid for 1 year):\n"
        "sk-ant-oat01-AAAABBBBCCCC\n"
        "DDDDEEEEFFFF\n"
        "Storethistokensecurely.Youwon'tbeabletoseeitagain.\n"
    )

    assert _extract_auth_token(output) == "sk-ant-oat01-AAAABBBBCCCCDDDDEEEEFFFF"


def test_extract_auth_token_ignores_unscoped_token_like_output() -> None:
    """Random token-like strings should not be persisted as Claude OAuth tokens."""
    from orcheo_backend.worker.external_agents import _extract_auth_token

    output = "unexpected debug output sk-ant-not-a-real-oauth-token"

    assert _extract_auth_token(output) is None


def test_extract_auth_token_prefers_explicit_oauth_block_over_earlier_token() -> None:
    """The final minted OAuth token block should win over earlier token-like text."""
    from orcheo_backend.worker.external_agents import _extract_auth_token

    output = (
        "unexpected sk-ant-stale-token\n"
        "Your OAuth token (valid for 1 year):\n"
        "sk-ant-oat01-fresh-token\n"
        "Store this token securely.\n"
    )

    assert _extract_auth_token(output) == "sk-ant-oat01-fresh-token"


def test_extract_auth_token_from_realistic_claude_terminal_output() -> None:
    """Claude PTY control characters and wraps should not break token extraction."""
    from orcheo_backend.worker.external_agents import _extract_auth_token, _strip_ansi

    sample = (
        "\x1b[1BYour OAuth tok\x1cn (valid for 1 year):\r\n"
        "\x1b[1Bsk-ant-oat01-KchzHxrSaiGhhAJzDpPvnUSIkTu53Ccs1FfMpIzU_"
        "kyjOlEzgyEBOcztFJEnGbAeaNv\r\n"
        "\x1b[1BUevvlND\x1cwP7tnbNlF\x1cw-lk7qMwAA\r\n"
        "\x1b[1BStore\x1cthis\x1ctoken\x1csecurely.\x1cYou\x1cwon't"
        "\x1cbe\x1cable\x1cto\x1csee\x1cit\x1cagain.\r\n"
    )

    assert _extract_auth_token(_strip_ansi(sample)) == (
        "sk-ant-oat01-KchzHxrSaiGhhAJzDpPvnUSIkTu53Ccs1FfMpIzU_"
        "kyjOlEzgyEBOcztFJEnGbAeaNvUevvlNDwP7tnbNlFw-lk7qMwAA"
    )


def test_extract_auth_token_from_setup_token_output_matches_manual_vm_shape() -> None:
    """Wrapped setup-token output should reconstruct the full token with no drops."""
    from orcheo_backend.worker.external_agents import _extract_auth_token

    output = (
        "✓ Long-lived authentication token created successfully!\n\n"
        "Your OAuth token (valid for 1 year):\n\n"
        "sk-ant-oat01-uotT3f8Nx5pzzxXkQx8uq5pFbuYUYQtmdQnFNvJncndBq7qacSnbCPeod_6E9ruJD4Pe\n"
        "oyuK7ALfpU9CeGy67A-7iX7ZgAA\n\n"
        "Store this token securely. You won't be able to see it again.\n\n"
        "Use this token by setting: export CLAUDE_CODE_OAUTH_TOKEN=<token>\n"
    )

    assert _extract_auth_token(output) == (
        "sk-ant-oat01-uotT3f8Nx5pzzxXkQx8uq5pFbuYUYQtmdQnFNvJncndBq7qacSnbCPeod_6E9ruJD4Pe"
        "oyuK7ALfpU9CeGy67A-7iX7ZgAA"
    )


def test_extract_auth_token_ignores_non_token_text_within_token_block() -> None:
    """Only token segments inside the token block should be concatenated."""
    from orcheo_backend.worker.external_agents import _extract_auth_token

    output = (
        "Your OAuth token (valid for 1 year):\n"
        "copy this carefully\n"
        "sk-ant-oat01-AAAABBBB\n"
        "CCCCDDDD\n"
        "Store this token securely.\n"
    )

    assert _extract_auth_token(output) == "sk-ant-oat01-AAAABBBBCCCCDDDD"


def test_extract_auth_token_keeps_suffix_before_store_marker_on_same_line() -> None:
    """Token suffix should not be dropped if the storage warning shares a line."""
    from orcheo_backend.worker.external_agents import _extract_auth_token

    output = (
        "Your OAuth token (valid for 1 year):\n"
        "sk-ant-oat01-AAAABBBB\n"
        "CCCCDDDDZZStore this token securely. You won't be able to see it again.\n"
    )

    assert _extract_auth_token(output) == "sk-ant-oat01-AAAABBBBCCCCDDDDZZ"


def test_extract_auth_token_when_header_and_token_share_the_same_line() -> None:
    """Token extraction should work when Claude starts the token after the colon."""
    from orcheo_backend.worker.external_agents import _extract_auth_token

    output = (
        "Your OAuth token (valid for 1 year): sk-ant-oat01-AAAABBBB\n"
        "CCCCDDDD\n"
        "Store this token securely.\n"
    )

    assert _extract_auth_token(output) == "sk-ant-oat01-AAAABBBBCCCCDDDD"


def test_run_login_command_submits_carriage_return_for_raw_tty_input() -> None:
    """Worker input forwarding should submit Enter as carriage return."""
    from orcheo_backend.worker.external_agents import _run_login_command

    script = (
        "import os, sys, termios, tty\n"
        "fd = sys.stdin.fileno()\n"
        "old = termios.tcgetattr(fd)\n"
        "tty.setraw(fd)\n"
        "sys.stdout.write('Paste code> ')\n"
        "sys.stdout.flush()\n"
        "chars = []\n"
        "try:\n"
        "    while True:\n"
        "        ch = os.read(fd, 1)\n"
        "        if not ch:\n"
        "            break\n"
        "        if ch == b'\\r':\n"
        "            print('ENTER-CR:' + ''.join(chars), flush=True)\n"
        "            break\n"
        "        if ch == b'\\n':\n"
        "            print('ENTER-LF:' + ''.join(chars), flush=True)\n"
        "            break\n"
        "        chars.append(ch.decode('utf-8', 'replace'))\n"
        "finally:\n"
        "    termios.tcsetattr(fd, termios.TCSADRAIN, old)\n"
    )
    queued = {"value": "ABCD-1234"}

    def on_output(_: str, __: str | None, ___: str | None) -> None:
        return None

    def consume_input(clear: bool) -> str | None:
        if clear:
            queued["value"] = None
            return None
        return queued["value"]

    result = _run_login_command(
        ["python3", "-c", script],
        env={},
        on_output=on_output,
        consume_input=consume_input,
        timeout_seconds=10,
    )

    assert "ENTER-CR:ABCD-1234" in result.output
    assert "ENTER-LF:ABCD-1234" not in result.output


@pytest.mark.asyncio
async def test_start_login_clears_stale_claude_oauth_token_before_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit Claude login should clear a stale stored OAuth token first."""
    from orcheo.external_agents.models import (
        AuthProbeResult,
        AuthStatus,
        ResolvedRuntime,
    )
    from orcheo_backend.worker.external_agents import start_external_agent_login_async

    store = ExternalAgentRuntimeStore()
    store._redis = None
    now = datetime.now(UTC)
    session = ExternalAgentLoginSession(
        session_id="fresh-claude-login",
        provider=ExternalAgentProviderName.CLAUDE_CODE,
        display_name="Claude Code",
        state=ExternalAgentLoginSessionState.PENDING,
        created_at=now,
        updated_at=now,
    )
    store.save_login_session(session)
    store.save_provider_environment(
        ExternalAgentProviderName.CLAUDE_CODE,
        {"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-stale-token"},
    )

    monkeypatch.setattr(
        "orcheo_backend.worker.external_agents.get_external_agent_runtime_store",
        lambda: store,
    )

    runtime = ResolvedRuntime(
        provider="claude_code",
        version="2.1.89",
        install_dir=Path("/root/.orcheo/agent-runtimes/claude_code"),
        executable_path=Path("/root/.orcheo/agent-runtimes/claude"),
        package_name="@anthropic-ai/claude-code",
    )
    provider = MagicMock()
    provider.probe_auth.return_value = AuthProbeResult(
        status=AuthStatus.SETUP_NEEDED,
        message="login required",
    )
    provider.oauth_login_command.return_value = ["/root/.orcheo/agent-runtimes/claude"]

    manager = MagicMock()
    manager.get_provider.return_value = provider
    manager.inspect_runtime.return_value = (runtime, None)
    manager.environment_for_provider.return_value = {}
    monkeypatch.setattr(
        "orcheo_backend.worker.external_agents.ExternalAgentRuntimeManager",
        lambda **kwargs: manager,
    )
    monkeypatch.setattr(
        "orcheo_backend.worker.external_agents._run_login_command",
        lambda *args, **kwargs: MagicMock(
            auth_token=None,
            auth_url=None,
            device_code=None,
            output="",
            timed_out=True,
        ),
    )

    result = await start_external_agent_login_async("claude_code", "fresh-claude-login")

    assert result == {"status": "timed_out"}
    manager.save_provider_environment.assert_called_once_with(
        "claude_code",
        {"CLAUDE_CODE_OAUTH_TOKEN": ""},
    )
    assert store.get_provider_environment(ExternalAgentProviderName.CLAUDE_CODE) == {}


@pytest.mark.asyncio
async def test_refresh_status_preserves_active_login_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refreshing status should not clobber an in-flight worker login session."""
    from orcheo_backend.worker.external_agents import (
        refresh_external_agent_status_async,
    )

    store = ExternalAgentRuntimeStore()
    store._redis = None
    now = datetime.now(UTC)
    session = ExternalAgentLoginSession(
        session_id="session-claude",
        provider=ExternalAgentProviderName.CLAUDE_CODE,
        display_name="Claude Code",
        state=ExternalAgentLoginSessionState.AWAITING_OAUTH,
        created_at=now,
        updated_at=now,
        auth_url="https://claude.com/cai/oauth/authorize?state=test-state",
        detail="Complete the browser sign-in.",
        recent_output="Opening browser to sign in...",
        resolved_version="2.1.89",
        executable_path="/root/.orcheo/agent-runtimes/claude",
    )
    store.save_login_session(session)
    store.save_provider_status(
        ExternalAgentProviderStatus(
            provider=ExternalAgentProviderName.CLAUDE_CODE,
            display_name="Claude Code",
            state=ExternalAgentProviderState.AUTHENTICATING,
            installed=True,
            authenticated=False,
            resolved_version="2.1.89",
            executable_path="/root/.orcheo/agent-runtimes/claude",
            detail="Waiting for browser-based sign-in.",
            active_session_id=session.session_id,
            checked_at=now,
        )
    )

    monkeypatch.setattr(
        "orcheo_backend.worker.external_agents.get_external_agent_runtime_store",
        lambda: store,
    )

    manager = MagicMock()
    manager.get_provider.return_value = MagicMock()
    monkeypatch.setattr(
        "orcheo_backend.worker.external_agents.ExternalAgentRuntimeManager",
        lambda **kwargs: manager,
    )

    result = await refresh_external_agent_status_async("claude_code")

    assert result == {"status": "authenticating"}
    manager.inspect_runtime.assert_not_called()
    status = store.get_provider_status(ExternalAgentProviderName.CLAUDE_CODE)
    assert status.active_session_id == session.session_id
    assert status.state == ExternalAgentProviderState.AUTHENTICATING


@pytest.mark.asyncio
async def test_refresh_status_drops_stale_login_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stale session snapshots should not keep the provider spinning forever."""
    from orcheo.external_agents.models import (
        AuthProbeResult,
        AuthStatus,
        ResolvedRuntime,
    )
    from orcheo_backend.worker.external_agents import (
        refresh_external_agent_status_async,
    )

    store = ExternalAgentRuntimeStore()
    store._redis = None
    now = datetime.now(UTC)
    stale_time = now - timedelta(seconds=30)
    session = ExternalAgentLoginSession(
        session_id="stale-session",
        provider=ExternalAgentProviderName.CLAUDE_CODE,
        display_name="Claude Code",
        state=ExternalAgentLoginSessionState.AWAITING_OAUTH,
        created_at=stale_time,
        updated_at=stale_time,
        auth_url="https://claude.com/cai/oauth/authorize?state=test-state",
        detail="Complete the browser sign-in.",
        resolved_version="2.1.89",
        executable_path="/root/.orcheo/agent-runtimes/claude",
    )
    store.save_login_session(session)
    store.save_provider_status(
        ExternalAgentProviderStatus(
            provider=ExternalAgentProviderName.CLAUDE_CODE,
            display_name="Claude Code",
            state=ExternalAgentProviderState.AUTHENTICATING,
            installed=True,
            authenticated=False,
            resolved_version="2.1.89",
            executable_path="/root/.orcheo/agent-runtimes/claude",
            detail="Waiting for browser-based sign-in.",
            active_session_id=session.session_id,
            checked_at=stale_time,
        )
    )

    monkeypatch.setattr(
        "orcheo_backend.worker.external_agents.get_external_agent_runtime_store",
        lambda: store,
    )

    runtime = ResolvedRuntime(
        provider="claude_code",
        version="2.1.89",
        install_dir=Path("/root/.orcheo/agent-runtimes/claude_code"),
        executable_path=Path("/root/.orcheo/agent-runtimes/claude"),
        package_name="@anthropic-ai/claude-code",
    )
    provider = MagicMock()
    provider.probe_auth.return_value = AuthProbeResult(
        status=AuthStatus.SETUP_NEEDED,
        message="Claude Code is installed but not authenticated on this worker.",
    )
    manager = MagicMock()
    manager.get_provider.return_value = provider
    manager.inspect_runtime.return_value = (runtime, None)
    monkeypatch.setattr(
        "orcheo_backend.worker.external_agents.ExternalAgentRuntimeManager",
        lambda **kwargs: manager,
    )

    result = await refresh_external_agent_status_async("claude_code")

    assert result == {"status": "needs_login"}
    manager.inspect_runtime.assert_called_once_with("claude_code")
