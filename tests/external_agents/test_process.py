"""Tests for managed process helpers used by external agent runtimes."""

from __future__ import annotations
import asyncio
import os
import signal
import sys
import pytest
from orcheo.external_agents.process import (
    _read_stream,
    _terminate_process_group,
    execute_process,
)


@pytest.mark.asyncio
async def test_execute_process_captures_stdout_and_stderr() -> None:
    """Stdout and stderr from the subprocess should be returned in the result."""
    result = await execute_process(
        [
            sys.executable,
            "-c",
            "import sys; print('out'); print('err', file=sys.stderr)",
        ]
    )

    assert result.stdout.strip() == "out"
    assert "err" in result.stderr
    assert result.exit_code == 0
    assert result.timed_out is False


@pytest.mark.asyncio
async def test_execute_process_handles_timeout() -> None:
    """Long-running processes are terminated when the timeout triggers."""
    result = await execute_process(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        timeout_seconds=0.1,
    )

    assert result.timed_out is True
    assert result.exit_code is not None


@pytest.mark.asyncio
async def test_read_stream_no_stream_returns_immediately() -> None:
    """The reader should exit gracefully when no stream is provided."""
    chunks: list[bytes] = []
    await _read_stream(None, chunks)
    assert chunks == []


@pytest.mark.asyncio
async def test_terminate_process_group_returns_cached_returncode(monkeypatch) -> None:
    """If the process already terminated, the cached return code is returned."""

    class DummyProcess:
        def __init__(self) -> None:
            self.pid = 12345
            self.returncode = 7

        async def wait(self) -> int:
            raise AssertionError("wait should not be called when returncode is set")

    result = await _terminate_process_group(DummyProcess())
    assert result == 7


@pytest.mark.asyncio
async def test_terminate_process_group_retries_after_timeout(monkeypatch) -> None:
    """The process group is SIGTERM'd and SIGKILL'd if it does not exit promptly."""
    killed: list[tuple[int, int]] = []

    class DummyProcess:
        def __init__(self) -> None:
            self.pid = 1
            self.returncode: int | None = None

        async def wait(self) -> int:
            self.returncode = 42
            return 42

    def fake_killpg(pid: int, sig: int) -> None:
        killed.append((pid, sig))

    async def fake_wait_for(coro: asyncio.Future[int], timeout: int | float) -> int:
        coro.close()
        raise TimeoutError

    monkeypatch.setattr(os, "killpg", fake_killpg)
    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)

    result = await _terminate_process_group(DummyProcess())

    assert result == 42
    assert killed == [(1, signal.SIGTERM), (1, signal.SIGKILL)]
