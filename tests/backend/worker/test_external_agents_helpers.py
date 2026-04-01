import os
import signal
import subprocess
from datetime import UTC, datetime
from types import SimpleNamespace
import pytest
from orcheo_backend.app.external_agent_runtime_store import ExternalAgentRuntimeStore
from orcheo_backend.app.schemas.system import (
    ExternalAgentLoginSession,
    ExternalAgentLoginSessionState,
    ExternalAgentProviderName,
)
from orcheo_backend.worker.external_agents import (
    LOGIN_INPUT_RESEND_SECONDS,
    _active_login_session_status,
    _browser_login_detail,
    _clear_stored_claude_oauth_token,
    _drain_login_output,
    _extract_auth_token,
    _extract_auth_url,
    _extract_device_code,
    _extract_token_segment_from_line,
    _extract_visible_auth_token,
    _extract_worker_auth_token,
    _forward_login_input,
    _initial_login_detail,
    _normalize_terminal_line,
    _prefix_before_store_marker,
    _redact_sensitive_output,
    _terminate_process_group,
    _token_line_after_header,
    _trim_recent_output,
)


@pytest.fixture
def runtime_store() -> ExternalAgentRuntimeStore:
    store = ExternalAgentRuntimeStore()
    store._redis = None
    return store


def test_extract_auth_url_prefers_public_link() -> None:
    payload = """https://localhost/auth
    some text
    https://example.com/auth?action=1"""
    assert _extract_auth_url(payload) == "https://example.com/auth?action=1"


def test_extract_auth_url_returns_localhost_when_it_is_the_only_match() -> None:
    assert (
        _extract_auth_url("Open http://localhost:1455/auth to continue")
        == "http://localhost:1455/auth"
    )


def test_extract_auth_url_stops_after_second_blank_continuation_line() -> None:
    payload = """https://example.com/path

part-one


part-two"""
    assert _extract_auth_url(payload) == "https://example.com/pathpart-one"


def test_extract_device_code() -> None:
    payload = "Use CODE-ABCD-1234-XYZ to authenticate"
    assert _extract_device_code(payload) == "CODE-ABCD-1234-XYZ"


@pytest.mark.parametrize(
    "token_block",
    [
        "Your OAuth token (valid for 1 year):\nsk-ant-AAA\nStore this token securely.",
        "valid for 1 year):\nsk-ant-BBB\nStore this token securely.",
        "CLAUDE_CODE_OAUTH_TOKEN=sk-ant-CCC",
    ],
)
def test_extract_auth_token_blocks(token_block: str) -> None:
    token = _extract_auth_token(token_block)
    assert token is not None and token.startswith("sk-ant-")


def test_extract_auth_token_rebuilds_collapsed_block_when_line_parser_misses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "orcheo_backend.worker.external_agents._extract_claude_oauth_token_from_lines",
        lambda output: None,
    )

    output = (
        "Your OAuth token (valid for 1 year): sk-ant-AAA BBB Store this token securely."
    )

    assert _extract_auth_token(output) == "sk-ant-AAABBB"


def test_extract_auth_token_ignores_fuzzy_block_without_real_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "orcheo_backend.worker.external_agents._extract_claude_oauth_token_from_lines",
        lambda output: None,
    )

    output = "valid for 1 year):\nnot-a-token\nStore this token securely.\n"

    assert _extract_auth_token(output) is None


def test_extract_auth_token_ignores_strict_block_without_claude_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "orcheo_backend.worker.external_agents._extract_claude_oauth_token_from_lines",
        lambda output: None,
    )

    output = (
        "Your OAuth token (valid for 1 year):\n"
        "not-a-claude-token\n"
        "Store this token securely.\n"
    )

    assert _extract_auth_token(output) is None


def test_extract_visible_auth_token_handles_masked() -> None:
    masked = (
        "Your OAuth token (valid for 1 year): sk-ant-***\nStore this token securely."
    )
    assert _extract_visible_auth_token(masked) is None


def test_extract_visible_auth_token_handles_masked_fuzzy_block() -> None:
    masked = "valid for 1 year):\nsk-ant-***\nStore this token securely."
    assert _extract_visible_auth_token(masked) is None


def test_extract_visible_auth_token_unmasked() -> None:
    raw = "Your OAuth token (valid for 1 year): sk-ant-XYZ\nStore this token securely."
    assert _extract_visible_auth_token(raw) == "sk-ant-XYZ"


def test_extract_worker_auth_token_prefers_raw() -> None:
    raw = "CLAUDE_CODE_OAUTH_TOKEN=sk-ant-RAW"
    visible = (
        "Your OAuth token (valid for 1 year): sk-ant-***\nStore this token securely."
    )
    assert _extract_worker_auth_token(raw, visible) == "sk-ant-RAW"


def test_normalize_and_prefix_helpers() -> None:
    line = " Valid for 1 year: YOUROAUTH TOKEN: sk-ant-XYZ "
    normalized = _normalize_terminal_line(line)
    assert "validfor1year" in normalized
    prefix, saw = _prefix_before_store_marker("token store it")
    assert saw


def test_token_line_after_header_without_colon_returns_empty_string() -> None:
    assert _token_line_after_header("Your OAuth token (valid for 1 year)") == ""


def test_extract_token_segment_from_line_ignores_masked_candidate() -> None:
    segment, saw_prefix, saw_store, saw_new_prefix = _extract_token_segment_from_line(
        "sk-ant-***",
        saw_prefix=False,
    )
    assert segment is None
    assert saw_prefix is False
    assert saw_store is False
    assert saw_new_prefix is False


def test_redact_sensitive_output() -> None:
    secret = "CLAUDE_CODE_OAUTH_TOKEN=sk-ant-SECRET"
    assert "[redacted worker auth token]" in _redact_sensitive_output(secret)


def test_trim_recent_output() -> None:
    long_text = "a" * 5000
    trimmed = _trim_recent_output(long_text)
    assert len(trimmed) == len(long_text[-4000:])


def test_forward_login_input_sends_and_resends(monkeypatch) -> None:
    writes: list[tuple[int, bytes]] = []
    monkeypatch.setattr(os, "write", lambda fd, data: writes.append((fd, data)))
    now = 1000.0
    last_input, last_at, awaiting = _forward_login_input(
        1,
        queued_input="code",
        last_sent_input=None,
        last_sent_at=None,
        awaiting_output_after_input=False,
        now=now,
    )
    assert last_input == "code"
    assert awaiting
    last_input2, last_at2, awaiting2 = _forward_login_input(
        1,
        queued_input="code",
        last_sent_input=last_input,
        last_sent_at=now,
        awaiting_output_after_input=True,
        now=now + LOGIN_INPUT_RESEND_SECONDS + 0.1,
    )
    assert last_input2 == "code"


def test_login_detail_variants() -> None:
    assert "Codex" in _initial_login_detail(ExternalAgentProviderName.CODEX)
    assert _initial_login_detail(ExternalAgentProviderName.CLAUDE_CODE).startswith(
        "Starting the provider"
    )
    assert "Claude" in _browser_login_detail(ExternalAgentProviderName.CLAUDE_CODE)
    assert "device-auth page" in _browser_login_detail(ExternalAgentProviderName.CODEX)
    assert "browser sign-in" in _browser_login_detail("other")  # type: ignore[arg-type]


def test_clear_stored_claude_token(runtime_store: ExternalAgentRuntimeStore) -> None:
    runtime_store.save_provider_environment(
        ExternalAgentProviderName.CLAUDE_CODE,
        {"CLAUDE_CODE_OAUTH_TOKEN": "token"},
    )

    class DummyManager:
        def __init__(self) -> None:
            self.env: dict[str, dict[str, str]] = {}

        def save_provider_environment(
            self, provider: str, updates: dict[str, str]
        ) -> None:
            self.env[provider] = updates

    manager = DummyManager()
    _clear_stored_claude_oauth_token(manager, runtime_store)
    assert (
        runtime_store.get_provider_environment(ExternalAgentProviderName.CLAUDE_CODE)
        == {}
    )


def test_active_login_session_status(runtime_store: ExternalAgentRuntimeStore) -> None:
    now = datetime.now(UTC)
    session = ExternalAgentLoginSession(
        session_id="sess",
        provider=ExternalAgentProviderName.CLAUDE_CODE,
        display_name="Claude",
        state=ExternalAgentLoginSessionState.PENDING,
        created_at=now,
        updated_at=now,
    )
    runtime_store.save_login_session(session)
    runtime_store.save_provider_status(
        runtime_store.get_provider_status(
            ExternalAgentProviderName.CLAUDE_CODE
        ).model_copy(update={"active_session_id": "sess"})
    )
    status = _active_login_session_status(
        runtime_store,
        ExternalAgentProviderName.CLAUDE_CODE,
        checked_at=now,
    )
    assert status is not None
    assert status.active_session_id == "sess"


def test_active_login_session_status_returns_none_without_active_session(
    runtime_store: ExternalAgentRuntimeStore,
) -> None:
    now = datetime.now(UTC)
    assert (
        _active_login_session_status(
            runtime_store,
            ExternalAgentProviderName.CLAUDE_CODE,
            checked_at=now,
        )
        is None
    )


def test_active_login_session_status_returns_none_for_terminal_session(
    runtime_store: ExternalAgentRuntimeStore,
) -> None:
    now = datetime.now(UTC)
    session = ExternalAgentLoginSession(
        session_id="sess",
        provider=ExternalAgentProviderName.CLAUDE_CODE,
        display_name="Claude",
        state=ExternalAgentLoginSessionState.AUTHENTICATED,
        created_at=now,
        updated_at=now,
    )
    runtime_store.save_login_session(session)
    runtime_store.save_provider_status(
        runtime_store.get_provider_status(
            ExternalAgentProviderName.CLAUDE_CODE
        ).model_copy(update={"active_session_id": "sess"})
    )

    assert (
        _active_login_session_status(
            runtime_store,
            ExternalAgentProviderName.CLAUDE_CODE,
            checked_at=now,
        )
        is None
    )


def test_forward_login_input_returns_existing_state_when_no_send_is_needed() -> None:
    assert _forward_login_input(
        1,
        queued_input="code",
        last_sent_input="code",
        last_sent_at=1000.0,
        awaiting_output_after_input=False,
        now=1000.5,
    ) == ("code", 1000.0, False)


def test_drain_login_output_handles_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        os, "read", lambda fd, size: (_ for _ in ()).throw(OSError("boom"))
    )
    screen = SimpleNamespace(write=lambda chunk: None)
    outputs: list[tuple[str, str | None, str | None]] = []

    result = _drain_login_output(
        1,
        terminal_screen=screen,
        raw_output="existing",
        output="visible",
        auth_url=None,
        device_code=None,
        auth_token=None,
        on_output=lambda output, auth_url, device_code: outputs.append(
            (output, auth_url, device_code)
        ),
    )

    assert result == ("existing", "visible", None, None, None)
    assert outputs == []


def test_terminate_process_group_returns_when_process_already_exited() -> None:
    process = SimpleNamespace(poll=lambda: 0)
    _terminate_process_group(process)  # type: ignore[arg-type]


def test_terminate_process_group_ignores_missing_process_on_sigterm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def wait(timeout=0):
        return None

    process = SimpleNamespace(pid=123, poll=lambda: None, wait=wait)
    monkeypatch.setattr(
        os,
        "killpg",
        lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError()),
    )

    _terminate_process_group(process)  # type: ignore[arg-type]


def test_terminate_process_group_handles_timeout_and_missing_process_on_sigkill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def wait(timeout=0):
        calls.append(timeout)
        if len(calls) == 1:
            raise subprocess.TimeoutExpired(cmd="cmd", timeout=timeout)

    process = SimpleNamespace(pid=123, poll=lambda: None, wait=wait)
    kill_calls: list[tuple[int, signal.Signals]] = []

    def killpg(pid: int, sig: signal.Signals) -> None:
        kill_calls.append((pid, sig))
        if sig == signal.SIGKILL:
            raise ProcessLookupError()

    monkeypatch.setattr(os, "killpg", killpg)

    _terminate_process_group(process)  # type: ignore[arg-type]

    assert kill_calls[0] == (123, signal.SIGTERM)
    assert kill_calls[1] == (123, signal.SIGKILL)


def test_terminate_process_group_waits_after_sigkill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def wait(timeout=0):
        calls.append(timeout)
        if len(calls) == 1:
            raise subprocess.TimeoutExpired(cmd="cmd", timeout=timeout)

    process = SimpleNamespace(pid=123, poll=lambda: None, wait=wait)
    monkeypatch.setattr(os, "killpg", lambda pid, sig: None)

    _terminate_process_group(process)  # type: ignore[arg-type]

    assert calls == [2, 2]
