"""Tests for Playwright-backed browser nodes."""

from __future__ import annotations
import os
from pathlib import Path
from typing import Any
import pytest
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes import browser as browser_nodes
from orcheo.nodes.browser import (
    BrowserActionNode,
    BrowserCloseNode,
    BrowserExtractNode,
    BrowserNavigateNode,
    BrowserScriptNode,
    BrowserWaitNode,
)


class FakeResponse:
    """Simple Playwright response double."""

    def __init__(
        self,
        url: str,
        *,
        status: int = 200,
        ok: bool = True,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.url = url
        self.status = status
        self.ok = ok
        self.headers = headers or {"content-type": "text/html"}


class FakeTracing:
    """Capture trace start and stop calls."""

    def __init__(self) -> None:
        self.start_kwargs: dict[str, Any] | None = None
        self.stop_path: str | None = None

    async def start(self, **kwargs: Any) -> None:
        self.start_kwargs = kwargs

    async def stop(self, path: str | None = None) -> None:
        self.stop_path = path


class FakeLocator:
    """Minimal locator double used by the browser nodes."""

    def __init__(self, page: FakePage, selector: str) -> None:
        self._page = page
        self._selector = selector

    async def click(self, **kwargs: Any) -> None:
        self._page.actions.append(("click", self._selector, None, kwargs))

    async def fill(self, value: str, **kwargs: Any) -> None:
        self._page.actions.append(("fill", self._selector, value, kwargs))

    async def press(self, value: str, **kwargs: Any) -> None:
        self._page.actions.append(("press", self._selector, value, kwargs))

    async def check(self, **kwargs: Any) -> None:
        self._page.actions.append(("check", self._selector, None, kwargs))

    async def uncheck(self, **kwargs: Any) -> None:
        self._page.actions.append(("uncheck", self._selector, None, kwargs))

    async def hover(self, **kwargs: Any) -> None:
        self._page.actions.append(("hover", self._selector, None, kwargs))

    async def select_option(self, value: Any, **kwargs: Any) -> None:
        self._page.actions.append(("select_option", self._selector, value, kwargs))

    async def set_input_files(self, value: Any, **kwargs: Any) -> None:
        self._page.actions.append(("set_input_files", self._selector, value, kwargs))

    async def wait_for(self, **kwargs: Any) -> None:
        self._page.wait_calls.append(("selector", self._selector, kwargs))

    async def inner_text(self) -> str:
        return self._page.text_values[self._selector]

    async def all_inner_texts(self) -> list[str]:
        return self._page.all_text_values[self._selector]

    async def inner_html(self) -> str:
        return self._page.html_values[self._selector]

    async def get_attribute(self, name: str) -> str | None:
        return self._page.attribute_values.get((self._selector, name))


class FakePage:
    """Minimal Playwright page double."""

    def __init__(self) -> None:
        self.url = "about:blank"
        self.title_text = "Blank"
        self.actions: list[tuple[str, str, Any, dict[str, Any]]] = []
        self.goto_calls: list[dict[str, Any]] = []
        self.wait_calls: list[tuple[str, Any, Any]] = []
        self.evaluate_calls: list[tuple[str, Any]] = []
        self.text_values = {"#result": "Orcheo"}
        self.all_text_values = {"li.item": ["one", "two"]}
        self.html_values = {"#result": "<span>Orcheo</span>"}
        self.attribute_values = {("#result", "href"): "https://example.com/item"}
        self.page_content = "<html><body>hello</body></html>"
        self.response_to_wait = FakeResponse(
            "https://example.com/api/ready",
            status=204,
            ok=True,
        )
        self.function_handle_payload: Any = None
        self.function_handle_disposed = False

    async def goto(self, url: str, **kwargs: Any) -> FakeResponse:
        self.url = url
        self.title_text = f"Title for {url}"
        self.goto_calls.append({"url": url, **kwargs})
        return FakeResponse(url)

    async def title(self) -> str:
        return self.title_text

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)

    async def content(self) -> str:
        return self.page_content

    async def wait_for_url(self, url_pattern: str, **kwargs: Any) -> None:
        self.wait_calls.append(("url", url_pattern, kwargs))

    async def wait_for_load_state(self, state: str, **kwargs: Any) -> None:
        self.wait_calls.append(("load_state", state, kwargs))

    async def wait_for_function(self, expression: str, **kwargs: Any) -> Any:
        self.wait_calls.append(("function", expression, kwargs))
        if self.function_handle_payload is None:
            return {"expression": expression, "arg": kwargs.get("arg")}
        return FakeJSHandle(self)

    async def wait_for_timeout(self, timeout: float) -> None:
        self.wait_calls.append(("timeout", timeout, {}))

    async def wait_for_response(self, predicate: Any, **kwargs: Any) -> FakeResponse:
        self.wait_calls.append(("response", self.response_to_wait.url, kwargs))
        assert predicate(self.response_to_wait) is True
        return self.response_to_wait

    async def evaluate(self, script: str, arg: Any = None) -> dict[str, Any]:
        self.evaluate_calls.append((script, arg))
        return {"script": script, "arg": arg}


class FakeContext:
    """Minimal browser context double."""

    def __init__(self, page: FakePage) -> None:
        self.page = page
        self.context_kwargs: dict[str, Any] | None = None
        self.closed = False
        self.tracing = FakeTracing()

    async def new_page(self) -> FakePage:
        return self.page

    async def close(self) -> None:
        self.closed = True


class FakeBrowser:
    """Minimal browser double."""

    def __init__(self, context: FakeContext) -> None:
        self.context = context
        self.closed = False
        self.context_kwargs: dict[str, Any] | None = None

    async def new_context(self, **kwargs: Any) -> FakeContext:
        self.context_kwargs = kwargs
        self.context.context_kwargs = kwargs
        return self.context

    async def close(self) -> None:
        self.closed = True


class FakeLauncher:
    """Minimal browser launcher double."""

    def __init__(self, browser: FakeBrowser) -> None:
        self.browser = browser
        self.launch_calls: list[dict[str, Any]] = []

    async def launch(self, **kwargs: Any) -> FakeBrowser:
        self.launch_calls.append(kwargs)
        return self.browser


class FakePlaywright:
    """Minimal Playwright runtime double."""

    def __init__(self) -> None:
        self.page = FakePage()
        self.context = FakeContext(self.page)
        self.browser = FakeBrowser(self.context)
        self.chromium = FakeLauncher(self.browser)
        self.firefox = FakeLauncher(self.browser)
        self.webkit = FakeLauncher(self.browser)
        self.stopped = False

    async def stop(self) -> None:
        self.stopped = True


class FakePlaywrightContextManager:
    """Return the fake Playwright runtime from .start()."""

    def __init__(self, playwright: FakePlaywright) -> None:
        self.playwright = playwright

    async def start(self) -> FakePlaywright:
        return self.playwright


class FakeJSHandle:
    """Minimal JSHandle double used by wait_for_function tests."""

    def __init__(self, page: FakePage) -> None:
        self._page = page

    async def json_value(self) -> Any:
        return self._page.function_handle_payload

    async def dispose(self) -> None:
        self._page.function_handle_disposed = True


@pytest.fixture
def fake_browser_runtime(monkeypatch: pytest.MonkeyPatch) -> FakePlaywright:
    """Reset the browser session manager and inject a fake Playwright runtime."""

    fake_playwright = FakePlaywright()
    monkeypatch.setattr(
        browser_nodes,
        "_browser_session_manager",
        browser_nodes.BrowserSessionManager(),
    )
    monkeypatch.setattr(
        browser_nodes,
        "_async_playwright_factory",
        lambda: lambda: FakePlaywrightContextManager(fake_playwright),
    )
    return fake_playwright


@pytest.mark.asyncio
async def test_browser_nodes_navigate_action_extract_and_close(
    fake_browser_runtime: FakePlaywright,
) -> None:
    """Browser nodes should create sessions, act, extract, and close cleanly."""

    state = State({"results": {}})
    config = RunnableConfig(configurable={"thread_id": "exec-1"})

    navigate = BrowserNavigateNode(
        name="navigate",
        url="https://example.com/dashboard",
        launch_args=["--disable-dev-shm-usage"],
        viewport_width=1280,
        viewport_height=720,
        extra_http_headers={"x-test": "1"},
        trace_path="/tmp/browser-trace.zip",
    )
    navigate_payload = (await navigate(state, config))["results"]["navigate"]

    assert navigate_payload["created_session"] is True
    assert navigate_payload["resolved_session_key"] == "exec-1:browser"
    assert navigate_payload["title"] == "Title for https://example.com/dashboard"
    assert navigate_payload["response"]["status"] == 200
    assert fake_browser_runtime.chromium.launch_calls == [
        {"headless": True, "args": ["--disable-dev-shm-usage"]}
    ]
    assert fake_browser_runtime.browser.context_kwargs == {
        "ignore_https_errors": False,
        "java_script_enabled": True,
        "viewport": {"width": 1280, "height": 720},
        "extra_http_headers": {"x-test": "1"},
    }
    assert fake_browser_runtime.context.tracing.start_kwargs == {
        "screenshots": True,
        "snapshots": True,
        "sources": True,
    }

    action = BrowserActionNode(
        name="action",
        action="fill",
        locator="#search",
        value="playwright",
    )
    action_payload = (await action(state, config))["results"]["action"]

    assert action_payload["action"] == "fill"
    assert fake_browser_runtime.page.actions[-1][0:3] == (
        "fill",
        "#search",
        "playwright",
    )

    extract = BrowserExtractNode(
        name="extract",
        mode="attribute",
        locator="#result",
        attribute_name="href",
    )
    extract_payload = (await extract(state, config))["results"]["extract"]

    assert extract_payload["value"] == "https://example.com/item"

    close = BrowserCloseNode(name="close")
    close_payload = (await close(state, config))["results"]["close"]

    assert close_payload["closed"] is True
    assert fake_browser_runtime.context.tracing.stop_path == "/tmp/browser-trace.zip"
    assert fake_browser_runtime.context.closed is True
    assert fake_browser_runtime.browser.closed is True
    assert fake_browser_runtime.stopped is True


@pytest.mark.asyncio
async def test_browser_wait_and_script_nodes_reuse_existing_session(
    fake_browser_runtime: FakePlaywright,
) -> None:
    """Wait and script nodes should operate on an existing Playwright session."""

    state = State({"results": {}})
    config = RunnableConfig(configurable={"thread_id": "exec-2"})
    await BrowserNavigateNode(
        name="navigate",
        url="https://example.com",
    )(state, config)

    selector_wait = BrowserWaitNode(
        name="wait_selector",
        wait_for="selector",
        locator="#result",
        selector_state="visible",
    )
    selector_payload = (await selector_wait(state, config))["results"]["wait_selector"]
    assert selector_payload["value"] == {"locator": "#result", "state": "visible"}

    function_wait = BrowserWaitNode(
        name="wait_function",
        wait_for="function",
        expression="() => window.ready === true",
        arg={"expected": True},
    )
    function_payload = (await function_wait(state, config))["results"]["wait_function"]
    assert function_payload["value"] == {
        "expression": "() => window.ready === true",
        "arg": {"expected": True},
    }

    response_wait = BrowserWaitNode(
        name="wait_response",
        wait_for="response",
        response_url="/api/ready",
        response_match_mode="contains",
        response_status=204,
    )
    response_payload = (await response_wait(state, config))["results"]["wait_response"]
    assert response_payload["value"] == {
        "url": "https://example.com/api/ready",
        "status": 204,
        "ok": True,
    }

    script = BrowserScriptNode(
        name="script",
        script="(payload) => payload.answer",
        arg={"answer": 42},
    )
    script_payload = (await script(state, config))["results"]["script"]
    assert script_payload["value"] == {
        "script": "(payload) => payload.answer",
        "arg": {"answer": 42},
    }


@pytest.mark.asyncio
async def test_browser_wait_for_function_serializes_handle(
    fake_browser_runtime: FakePlaywright,
) -> None:
    """Function waits should serialize and dispose returned JSHandle values."""

    state = State({"results": {}})
    config = RunnableConfig(configurable={"thread_id": "exec-serialized"})
    fake_browser_runtime.page.function_handle_payload = {
        "expression": "() => window.ready === true",
        "arg": {"expected": True},
    }

    await BrowserNavigateNode(
        name="navigate",
        url="https://example.com",
    )(state, config)

    function_wait = BrowserWaitNode(
        name="wait_function",
        wait_for="function",
        expression="() => window.ready === true",
        arg={"expected": True},
    )
    function_payload = (await function_wait(state, config))["results"]["wait_function"]
    assert function_payload["value"] == {
        "expression": "() => window.ready === true",
        "arg": {"expected": True},
    }
    assert fake_browser_runtime.page.function_handle_disposed is True


@pytest.mark.asyncio
async def test_browser_sessions_are_scoped_by_thread_id(
    fake_browser_runtime: FakePlaywright,
) -> None:
    """The default browser session id should be isolated per workflow run."""

    state = State({"results": {}})
    config_one = RunnableConfig(configurable={"thread_id": "exec-a"})
    config_two = RunnableConfig(configurable={"thread_id": "exec-b"})

    await BrowserNavigateNode(name="nav_a", url="https://example.com/a")(
        state, config_one
    )
    await BrowserNavigateNode(name="nav_b", url="https://example.com/b")(
        state, config_two
    )

    assert len(fake_browser_runtime.chromium.launch_calls) == 2


@pytest.mark.asyncio
async def test_browser_session_manager_closes_all_sessions_for_scope(
    fake_browser_runtime: FakePlaywright,
) -> None:
    """Closing one scope should tear down every associated browser session."""

    del fake_browser_runtime
    manager = browser_nodes.BrowserSessionManager()
    config = RunnableConfig(configurable={"thread_id": "exec-scope"})

    first, _ = await manager.get_or_create(
        key=browser_nodes._session_key("browser", config),
        browser_type="chromium",
        headless=True,
        launch_args=[],
        viewport_width=None,
        viewport_height=None,
        user_agent=None,
        locale=None,
        timezone_id=None,
        storage_state=None,
        extra_http_headers=None,
        ignore_https_errors=False,
        java_script_enabled=True,
        trace_path=None,
    )
    second, _ = await manager.get_or_create(
        key=browser_nodes._session_key("browser-2", config),
        browser_type="chromium",
        headless=True,
        launch_args=[],
        viewport_width=None,
        viewport_height=None,
        user_agent=None,
        locale=None,
        timezone_id=None,
        storage_state=None,
        extra_http_headers=None,
        ignore_https_errors=False,
        java_script_enabled=True,
        trace_path=None,
    )

    closed = await manager.close_scope("exec-scope")

    assert closed == 2
    assert first.context.closed is True
    assert second.context.closed is True


@pytest.mark.asyncio
async def test_browser_nodes_raise_when_session_is_missing() -> None:
    """Browser nodes should fail fast when no matching session exists."""

    state = State({"results": {}})
    action = BrowserActionNode(
        name="action",
        action="click",
        locator="#missing",
    )

    with pytest.raises(ValueError, match="BrowserNavigateNode first"):
        await action(state, RunnableConfig(configurable={"thread_id": "exec-404"}))


def test_configure_playwright_browser_path_uses_fallback_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Browser nodes should reuse a shared browser cache when HOME differs."""

    fallback_root = Path("/data/home/.cache/ms-playwright")
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.setattr(
        browser_nodes,
        "_playwright_browser_root_candidates",
        lambda: (Path("/missing"), fallback_root),
    )
    monkeypatch.setattr(
        browser_nodes,
        "_contains_playwright_browser_installation",
        lambda root, browser_type: root == fallback_root and browser_type == "chromium",
    )

    browser_nodes._configure_playwright_browser_path("chromium")

    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == str(fallback_root)


def test_configure_playwright_browser_path_keeps_valid_existing_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An existing valid Playwright browser cache should not be overwritten."""

    configured_root = Path("/ms-playwright")
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(configured_root))
    monkeypatch.setattr(
        browser_nodes,
        "_contains_playwright_browser_installation",
        lambda root, browser_type: root == configured_root
        and browser_type == "chromium",
    )

    browser_nodes._configure_playwright_browser_path("chromium")

    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == str(configured_root)
