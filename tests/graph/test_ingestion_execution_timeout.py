"""Tests for the ingestion execution timeout context manager."""

from __future__ import annotations
import itertools
import pytest
from orcheo.graph.ingestion import _execution_timeout


def test_execution_timeout_disabled_for_non_positive_values() -> None:
    with _execution_timeout(0):
        assert True


def test_execution_timeout_trace_fallback_enforces_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSys:
        def __init__(self) -> None:
            self._trace: object | None = None
            self.calls: list[object | None] = []

        def gettrace(self) -> object | None:
            return self._trace

        def settrace(self, trace: object | None) -> None:
            self.calls.append(trace)
            self._trace = trace

    class FakeThreading:
        def __init__(self) -> None:
            self._trace: object | None = None
            self._current_thread = object()
            self._main_thread = object()
            self.calls: list[object | None] = []

        def current_thread(self) -> object:
            return self._current_thread

        def main_thread(self) -> object:
            return self._main_thread

        def gettrace(self) -> object | None:
            return self._trace

        def settrace(self, trace: object | None) -> None:
            self.calls.append(trace)
            self._trace = trace

    fake_sys = FakeSys()
    fake_threading = FakeThreading()
    monkeypatch.setattr("orcheo.graph.ingestion.sys", fake_sys)
    monkeypatch.setattr("orcheo.graph.ingestion.threading", fake_threading)

    perf_counter_values = itertools.chain([0.0, 0.2], itertools.repeat(0.2))
    monkeypatch.setattr(
        "orcheo.graph.ingestion.time.perf_counter",
        lambda: next(perf_counter_values),
    )

    original_trace = fake_sys.gettrace()
    original_thread_trace = fake_threading.gettrace()

    with pytest.raises(TimeoutError):
        with _execution_timeout(0.1):
            trace = fake_sys.gettrace()
            assert callable(trace)
            next_trace = trace(None, "call", None)
            assert next_trace is trace
            next_trace(None, "line", None)

    assert fake_sys.gettrace() is original_trace
    assert fake_threading.gettrace() is original_thread_trace
    assert fake_sys.calls[-1] is None
    assert fake_threading.calls[-1] is None


def test_execution_timeout_restores_existing_traces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSys:
        def __init__(self) -> None:
            self._trace: object | None = object()
            self.calls: list[object | None] = []

        def gettrace(self) -> object | None:
            return self._trace

        def settrace(self, trace: object | None) -> None:
            self.calls.append(trace)
            self._trace = trace

    class FakeThreading:
        def __init__(self) -> None:
            self._trace: object | None = object()
            self._current_thread = object()
            self._main_thread = object()
            self.calls: list[object | None] = []

        def current_thread(self) -> object:
            return self._current_thread

        def main_thread(self) -> object:
            return self._main_thread

        def gettrace(self) -> object | None:
            return self._trace

        def settrace(self, trace: object | None) -> None:
            self.calls.append(trace)
            self._trace = trace

    fake_sys = FakeSys()
    fake_threading = FakeThreading()
    monkeypatch.setattr("orcheo.graph.ingestion.sys", fake_sys)
    monkeypatch.setattr("orcheo.graph.ingestion.threading", fake_threading)

    monkeypatch.setattr(
        "orcheo.graph.ingestion.time.perf_counter",
        lambda: 0.0,
    )

    original_trace = fake_sys.gettrace()
    original_thread_trace = fake_threading.gettrace()

    with _execution_timeout(0.1):
        trace = fake_sys.gettrace()
        assert callable(trace)
        returned = trace(None, "call", None)
        assert returned is trace

    assert fake_sys.gettrace() is original_trace
    assert fake_threading.gettrace() is original_thread_trace
    assert fake_sys.calls[-1] is original_trace
    assert fake_threading.calls[-1] is original_thread_trace
