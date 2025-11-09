import sys
from unittest.mock import MagicMock
import pytest
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.javascript_sandbox import JavaScriptSandboxNode


# Ensure py_mini_racer is importable in test environments without the dependency
if "py_mini_racer" not in sys.modules:
    mock_py_mini_racer_module = MagicMock()
    mock_py_mini_racer = MagicMock()
    mock_py_mini_racer_module.py_mini_racer = mock_py_mini_racer
    sys.modules["py_mini_racer"] = mock_py_mini_racer_module
    sys.modules["py_mini_racer.py_mini_racer"] = mock_py_mini_racer


@pytest.mark.asyncio
async def test_javascript_sandbox_executes_script(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JavaScriptSandboxNode should evaluate JS and capture console output."""

    class MockMiniRacer:
        def __init__(self):
            self.state = {
                "__ORCHEO_CONSOLE__": [],
                "input": 4,
                "doubled": None,
                "result": None,
            }

        def eval(self, code: str):  # noqa: PLR0911
            import json

            if "var __ORCHEO_CONSOLE__" in code and "console = {" in code:
                self.state["__ORCHEO_CONSOLE__"] = []
                return None
            if "var console = { log:" in code:
                return None
            if "var input = " in code:
                self.state["input"] = 4
                return None
            if code.strip().startswith("var doubled"):
                self.state["doubled"] = 8
                self.state["result"] = {"value": 8}
                self.state["__ORCHEO_CONSOLE__"].append("doubled 8")
                return None
            if "JSON.stringify((typeof result" in code:
                return json.dumps(self.state.get("result"))
            if "JSON.stringify(__ORCHEO_CONSOLE__)" in code:
                return json.dumps(self.state["__ORCHEO_CONSOLE__"])
            return None

    monkeypatch.setattr("py_mini_racer.py_mini_racer.MiniRacer", MockMiniRacer)
    monkeypatch.setattr("py_mini_racer.py_mini_racer.JSEvalException", Exception)

    node = JavaScriptSandboxNode(
        name="js_sandbox",
        script="""
var doubled = input * 2;
console.log('doubled', doubled);
var result = { value: doubled };
""",
        context={"input": 4},
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["js_sandbox"]

    assert payload["result"] == {"value": 8}
    assert payload["console"] == ["doubled 8"]


@pytest.mark.asyncio
async def test_javascript_sandbox_no_console_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JavaScriptSandboxNode should handle console capture disabled."""

    class MockMiniRacer:
        def __init__(self):
            self.state = {"result": 42}

        def eval(self, code: str):
            import json

            if "var console = { log: function() {} };" in code:
                return None
            if "var input = " in code:
                return None
            if "result = " in code or "var result" in code:
                return None
            if "JSON.stringify((typeof result" in code:
                return json.dumps(42)
            return None

    monkeypatch.setattr("py_mini_racer.py_mini_racer.MiniRacer", MockMiniRacer)
    monkeypatch.setattr("py_mini_racer.py_mini_racer.JSEvalException", Exception)

    node = JavaScriptSandboxNode(
        name="js_sandbox",
        script="var result = input + 2;",
        context={"input": 40},
        capture_console=False,
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["js_sandbox"]

    assert payload["result"] == 42
    assert payload["console"] == []


@pytest.mark.asyncio
async def test_javascript_sandbox_non_identifier_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JavaScriptSandboxNode should handle non-identifier context keys."""

    class MockMiniRacer:
        def __init__(self):
            self.state = {}

        def eval(self, code: str):
            import json

            if "var __ORCHEO_CONSOLE__" in code:
                return None
            if 'this["my-key"]' in code:
                self.state["my-key"] = 100
                return None
            if "var result" in code:
                self.state["result"] = 100
                return None
            if "JSON.stringify((typeof result" in code:
                return json.dumps(self.state.get("result"))
            if "JSON.stringify(__ORCHEO_CONSOLE__)" in code:
                return json.dumps([])
            return None

    monkeypatch.setattr("py_mini_racer.py_mini_racer.MiniRacer", MockMiniRacer)
    monkeypatch.setattr("py_mini_racer.py_mini_racer.JSEvalException", Exception)

    node = JavaScriptSandboxNode(
        name="js_sandbox",
        script="var result = this['my-key'];",
        context={"my-key": 100},
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["js_sandbox"]

    assert payload["result"] == 100


@pytest.mark.asyncio
async def test_javascript_sandbox_eval_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JavaScriptSandboxNode should handle JSEvalException during serialization."""

    class JSEvalError(Exception):
        pass

    class MockMiniRacer:
        def __init__(self):
            self.state = {"result": "not-json-serializable"}

        def eval(self, code: str):
            import json

            if "var __ORCHEO_CONSOLE__" in code:
                return None
            if "var result" in code:
                return None
            if "JSON.stringify((typeof result" in code:
                raise JSEvalError("Cannot serialize")
            if "typeof result === 'undefined'" in code:
                return "fallback_value"
            if "JSON.stringify(__ORCHEO_CONSOLE__)" in code:
                return json.dumps([])
            return None

    monkeypatch.setattr("py_mini_racer.py_mini_racer.MiniRacer", MockMiniRacer)
    monkeypatch.setattr("py_mini_racer.py_mini_racer.JSEvalException", JSEvalError)

    node = JavaScriptSandboxNode(
        name="js_sandbox",
        script="var result = function() {};",
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["js_sandbox"]

    assert payload["result"] == "fallback_value"
