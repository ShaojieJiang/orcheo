"""Shared helpers for workflow CLI tests."""

from __future__ import annotations
from typing import Any
from orcheo_sdk.cli.config import CLISettings
from orcheo_sdk.cli.state import CLIState


class StubConsole:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def print(self, *args: Any, **_: Any) -> None:
        text = " ".join(str(arg) for arg in args)
        self.messages.append(text)


class StubClient:
    def __init__(self) -> None:
        self.base_url = "http://api.test"
        self.responses: dict[str, Any] = {}
        self.calls: list[Any] = []

    def get(self, url: str) -> Any:
        self.calls.append(("GET", url))
        return self.responses[url]

    def post(self, url: str, **payload: Any) -> Any:
        self.calls.append(("POST", url, payload))
        raise NotImplementedError

    def delete(self, url: str) -> None:  # pragma: no cover - convenience helper
        self.calls.append(("DELETE", url))

    def get_active_token(self) -> str | None:
        return "token"


class DummyCtx:
    def __init__(self, state: CLIState) -> None:
        self._state = state

    def ensure_object(self, _: Any) -> CLIState:
        return self._state


def make_state(*, verbose_results: bool = False) -> CLIState:
    return CLIState(
        settings=CLISettings(
            api_url="http://api.test",
            service_token="token",
            profile="default",
            offline=False,
        ),
        client=StubClient(),
        cache=object(),
        console=StubConsole(),
        verbose_results=verbose_results,
    )


__all__ = ["DummyCtx", "StubClient", "StubConsole", "make_state"]
