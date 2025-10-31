import sys
from unittest.mock import MagicMock
import pytest
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.utility import (
    DebugNode,
    JavaScriptSandboxNode,
    PythonSandboxNode,
    SubWorkflowNode,
)


# Mock py_mini_racer module if not available
if "py_mini_racer" not in sys.modules:
    # Create a mock module with py_mini_racer submodule
    mock_py_mini_racer_module = MagicMock()
    mock_py_mini_racer = MagicMock()
    mock_py_mini_racer_module.py_mini_racer = mock_py_mini_racer
    sys.modules["py_mini_racer"] = mock_py_mini_racer_module
    sys.modules["py_mini_racer.py_mini_racer"] = mock_py_mini_racer


@pytest.mark.asyncio
async def test_python_sandbox_executes_source() -> None:
    """PythonSandboxNode should evaluate code and capture stdout."""

    node = PythonSandboxNode(
        name="python_sandbox",
        source="""
value = bindings_value * 2
print('value', value)
result = value
""",
        bindings={"bindings_value": 21},
        include_locals=True,
    )

    state = State({"results": {}, "inputs": {}})
    payload = (await node(state, RunnableConfig()))["results"]["python_sandbox"]

    assert payload["result"] == 42
    assert payload["stdout"] == ["value 42"]
    assert payload["locals"]["value"] == 42


@pytest.mark.asyncio
async def test_python_sandbox_exposes_state() -> None:
    """PythonSandboxNode should expose state when enabled."""

    node = PythonSandboxNode(
        name="python_sandbox",
        source="result = state['results']['count'] + 5",
        expose_state=True,
    )

    state = State({"results": {"count": 7}})
    payload = (await node(state, RunnableConfig()))["results"]["python_sandbox"]

    assert payload["result"] == 12


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

            # Handle different eval calls in order
            if "var __ORCHEO_CONSOLE__" in code and "console = {" in code:
                # Initial console setup
                self.state["__ORCHEO_CONSOLE__"] = []
                return None
            elif "var console = { log:" in code:
                # Alternative console setup
                return None
            elif "var input = " in code:
                # Setting up input variable
                self.state["input"] = 4
                return None
            elif code.strip().startswith("var doubled"):
                # Execute the script - accumulate console logs
                self.state["doubled"] = 8
                self.state["result"] = {"value": 8}
                self.state["__ORCHEO_CONSOLE__"].append("doubled 8")
                return None
            elif "JSON.stringify((typeof result" in code:
                # Return result
                return json.dumps(self.state.get("result"))
            elif "JSON.stringify(__ORCHEO_CONSOLE__)" in code:
                # Return console output
                return json.dumps(self.state["__ORCHEO_CONSOLE__"])
            return None

    # Mock py_mini_racer module
    mock_module = MagicMock()
    mock_module.MiniRacer = MockMiniRacer
    mock_module.JSEvalException = Exception
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
async def test_debug_node_taps_state_path() -> None:
    """DebugNode should tap into nested state values and include snapshots."""

    node = DebugNode(
        name="debug",
        message="Inspect value",
        tap_path="items.1.value",
        include_state=True,
    )

    state = State({"results": {"items": [{"value": 2}, {"value": 5}]}})
    payload = (await node(state, RunnableConfig()))["results"]["debug"]

    assert payload["message"] == "Inspect value"
    assert payload["found"] is True and payload["value"] == 5
    assert payload["state"]["results"]["items"][1]["value"] == 5


@pytest.mark.asyncio
async def test_sub_workflow_node_runs_steps_and_propagates() -> None:
    """SubWorkflowNode should execute configured steps sequentially."""

    node = SubWorkflowNode(
        name="sub",
        steps=[
            {
                "type": "SetVariableNode",
                "name": "initial",
                "variables": {"value": 3},
            },
            {
                "type": "SetVariableNode",
                "name": "derived",
                "variables": {
                    "value": "{{ results.initial.value }}",
                    "extra": 9,
                },
            },
        ],
        include_state=True,
        propagate_to_parent=True,
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["sub"]

    assert payload["result"] == {"value": 3, "extra": 9}
    assert [step["name"] for step in payload["steps"]] == ["initial", "derived"]
    assert state["results"]["derived"] == {"value": 3, "extra": 9}
    assert payload["state"]["results"]["derived"]["extra"] == 9


@pytest.mark.asyncio
async def test_sub_workflow_node_validates_step_configuration() -> None:
    """SubWorkflowNode should validate the supplied steps."""

    node = SubWorkflowNode(
        name="sub",
        steps=[{"name": "invalid"}],
    )

    state = State({"results": {}})
    with pytest.raises(ValueError):
        await node(state, RunnableConfig())


@pytest.mark.asyncio
async def test_python_sandbox_captures_stdout_disabled() -> None:
    """PythonSandboxNode should not capture stdout when disabled."""

    node = PythonSandboxNode(
        name="python_sandbox",
        source="""
print('this should not be captured')
result = 42
""",
        capture_stdout=False,
    )

    state = State({"results": {}, "inputs": {}})
    payload = (await node(state, RunnableConfig()))["results"]["python_sandbox"]

    assert payload["result"] == 42
    assert payload["stdout"] == []


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
            elif "var input = " in code:
                return None
            elif "result = " in code or "var result" in code:
                return None
            elif "JSON.stringify((typeof result" in code:
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
            elif 'this["my-key"]' in code:
                # Non-identifier key assignment
                self.state["my-key"] = 100
                return None
            elif "var result" in code:
                self.state["result"] = 100
                return None
            elif "JSON.stringify((typeof result" in code:
                return json.dumps(self.state.get("result"))
            elif "JSON.stringify(__ORCHEO_CONSOLE__)" in code:
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
    """JavaScriptSandboxNode should handle JSEvalException when serializing result."""

    class JSEvalError(Exception):
        pass

    class MockMiniRacer:
        def __init__(self):
            self.state = {"result": "not-json-serializable"}
            self.eval_count = 0

        def eval(self, code: str):
            import json

            if "var __ORCHEO_CONSOLE__" in code:
                return None
            elif "var result" in code:
                return None
            elif "JSON.stringify((typeof result" in code:
                # Raise exception on stringify attempt
                raise JSEvalError("Cannot serialize")
            elif "typeof result === 'undefined'" in code:
                # Fallback to direct eval
                return "fallback_value"
            elif "JSON.stringify(__ORCHEO_CONSOLE__)" in code:
                return json.dumps([])
            return None

    monkeypatch.setattr("py_mini_racer.py_mini_racer.MiniRacer", MockMiniRacer)
    monkeypatch.setattr("py_mini_racer.py_mini_racer.JSEvalException", JSEvalError)

    node = JavaScriptSandboxNode(
        name="js_sandbox",
        script="var result = function() {};",  # Functions can't be JSON serialized
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["js_sandbox"]

    # When JSON.stringify fails, it falls back to direct eval
    assert payload["result"] == "fallback_value"


@pytest.mark.asyncio
async def test_debug_node_empty_path_error() -> None:
    """DebugNode should raise ValueError for empty tap_path."""

    node = DebugNode(
        name="debug",
        tap_path="",
    )

    state = State({"results": {}})
    with pytest.raises(ValueError, match="tap_path must be a non-empty string"):
        await node(state, RunnableConfig())


@pytest.mark.asyncio
async def test_debug_node_whitespace_only_path_error() -> None:
    """DebugNode should raise ValueError for whitespace-only tap_path."""

    node = DebugNode(
        name="debug",
        tap_path="   ",
    )

    state = State({"results": {}})
    with pytest.raises(ValueError, match="tap_path must contain at least one segment"):
        await node(state, RunnableConfig())


@pytest.mark.asyncio
async def test_debug_node_invalid_sequence_index() -> None:
    """DebugNode should handle invalid sequence index gracefully."""

    node = DebugNode(
        name="debug",
        tap_path="items.invalid_index",
    )

    state = State({"results": {"items": [1, 2, 3]}})
    payload = (await node(state, RunnableConfig()))["results"]["debug"]

    assert payload["found"] is False
    assert payload["value"] is None


@pytest.mark.asyncio
async def test_debug_node_out_of_bounds_index() -> None:
    """DebugNode should handle out-of-bounds sequence index."""

    node = DebugNode(
        name="debug",
        tap_path="items.10",
    )

    state = State({"results": {"items": [1, 2, 3]}})
    payload = (await node(state, RunnableConfig()))["results"]["debug"]

    assert payload["found"] is False
    assert payload["value"] is None


@pytest.mark.asyncio
async def test_debug_node_negative_index() -> None:
    """DebugNode should handle negative sequence index."""

    node = DebugNode(
        name="debug",
        tap_path="items.-1",
    )

    state = State({"results": {"items": [1, 2, 3]}})
    payload = (await node(state, RunnableConfig()))["results"]["debug"]

    assert payload["found"] is False
    assert payload["value"] is None


@pytest.mark.asyncio
async def test_debug_node_path_not_found() -> None:
    """DebugNode should handle non-existent path."""

    node = DebugNode(
        name="debug",
        tap_path="nonexistent.path",
    )

    state = State({"results": {"items": [1, 2, 3]}})
    payload = (await node(state, RunnableConfig()))["results"]["debug"]

    assert payload["found"] is False
    assert payload["value"] is None


@pytest.mark.asyncio
async def test_debug_node_no_tap_path() -> None:
    """DebugNode should work without tap_path."""

    node = DebugNode(
        name="debug",
        message="Just a message",
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["debug"]

    assert payload["message"] == "Just a message"
    assert payload["tap_path"] is None
    assert payload["found"] is False


@pytest.mark.asyncio
async def test_debug_node_include_state_disabled() -> None:
    """DebugNode should not include state when disabled."""

    node = DebugNode(
        name="debug",
        message="Test",
        include_state=False,
    )

    state = State({"results": {"data": "value"}})
    payload = (await node(state, RunnableConfig()))["results"]["debug"]

    assert "state" not in payload


@pytest.mark.asyncio
async def test_sub_workflow_node_empty_steps() -> None:
    """SubWorkflowNode should handle empty steps list."""

    node = SubWorkflowNode(
        name="sub",
        steps=[],
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["sub"]

    assert payload == {"steps": [], "result": None}


@pytest.mark.asyncio
async def test_sub_workflow_node_unknown_node_type() -> None:
    """SubWorkflowNode should raise ValueError for unknown node type."""

    node = SubWorkflowNode(
        name="sub",
        steps=[{"type": "NonExistentNode", "name": "test"}],
    )

    state = State({"results": {}})
    with pytest.raises(ValueError, match="Unknown node type"):
        await node(state, RunnableConfig())


@pytest.mark.asyncio
async def test_sub_workflow_node_propagate_updates_parent() -> None:
    """SubWorkflowNode should propagate results to parent state when enabled."""

    node = SubWorkflowNode(
        name="sub",
        steps=[
            {
                "type": "SetVariableNode",
                "name": "step1",
                "variables": {"value": 42},
            },
        ],
        propagate_to_parent=True,
    )

    state = State({"results": {"existing": "data"}})
    await node(state, RunnableConfig())

    # Should propagate step results to parent state
    assert state["results"]["step1"] == {"value": 42}
    assert state["results"]["existing"] == "data"


@pytest.mark.asyncio
async def test_sub_workflow_node_custom_result_step() -> None:
    """SubWorkflowNode should return result from specified step."""

    node = SubWorkflowNode(
        name="sub",
        steps=[
            {
                "type": "SetVariableNode",
                "name": "first",
                "variables": {"value": 1},
            },
            {
                "type": "SetVariableNode",
                "name": "second",
                "variables": {"value": 2},
            },
        ],
        result_step="first",
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["sub"]

    assert payload["result"] == {"value": 1}


@pytest.mark.asyncio
async def test_sub_workflow_node_include_state_disabled() -> None:
    """SubWorkflowNode should not include state when disabled."""

    node = SubWorkflowNode(
        name="sub",
        steps=[
            {
                "type": "SetVariableNode",
                "name": "step1",
                "variables": {"value": 42},
            },
        ],
        include_state=False,
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["sub"]

    assert "state" not in payload


@pytest.mark.asyncio
async def test_debug_node_with_message_only() -> None:
    """DebugNode should log message when message is set but tap_path is not."""

    node = DebugNode(
        name="debug",
        message="Debug message only",
        tap_path=None,
    )

    state = State({"results": {"data": "value"}})
    payload = (await node(state, RunnableConfig()))["results"]["debug"]

    assert payload["message"] == "Debug message only"
    assert payload["tap_path"] is None


@pytest.mark.asyncio
async def test_python_sandbox_print_collector_variants() -> None:
    """PythonSandboxNode should handle various print collector states."""

    # Test with multiple print statements
    node = PythonSandboxNode(
        name="python_sandbox",
        source="""
print('line 1')
print('line 2')
print('line 3')
result = 'done'
""",
        capture_stdout=True,
    )

    state = State({"results": {}, "inputs": {}})
    payload = (await node(state, RunnableConfig()))["results"]["python_sandbox"]

    assert payload["result"] == "done"
    assert len(payload["stdout"]) == 3
    assert "line 1" in payload["stdout"]


@pytest.mark.asyncio
async def test_python_sandbox_no_print_output() -> None:
    """PythonSandboxNode handles PrintCollector with no output (empty captured)."""

    # This test covers line 141->150: PrintCollector exists but captured is empty
    # This happens when print() is called but _print.txt doesn't contain anything
    # We can trigger this by mocking a PrintCollector with empty txt

    from unittest.mock import patch
    from RestrictedPython.PrintCollector import PrintCollector

    original_exec = exec

    def mock_exec(bytecode, globals_dict, locals_dict):
        original_exec(bytecode, globals_dict, locals_dict)
        # Create a real PrintCollector instance and set txt to empty
        collector = PrintCollector()
        collector.txt = []  # Empty list means no captured output
        locals_dict["_print"] = collector

    with patch("builtins.exec", side_effect=mock_exec):
        node = PythonSandboxNode(
            name="python_sandbox",
            source="result = 21 * 2",
            capture_stdout=True,
        )

        state = State({"results": {}, "inputs": {}})
        payload = (await node(state, RunnableConfig()))["results"]["python_sandbox"]

        assert payload["result"] == 42
        # captured is empty (line 141 is False), so stdout should be []
        assert payload["stdout"] == []


@pytest.mark.asyncio
async def test_debug_node_logs_with_message_and_tap_path() -> None:
    """DebugNode should log when both message and tap_path are provided."""

    node = DebugNode(
        name="debug",
        message="Checking value",
        tap_path="data.value",
    )

    state = State({"results": {"data": {"value": 123}}})
    payload = (await node(state, RunnableConfig()))["results"]["debug"]

    assert payload["message"] == "Checking value"
    assert payload["tap_path"] == "data.value"
    assert payload["found"] is True
    assert payload["value"] == 123


@pytest.mark.asyncio
async def test_debug_node_normalise_state_with_mapping_inputs() -> None:
    """DebugNode should normalise state with both inputs and results as Mappings."""

    node = DebugNode(
        name="debug",
        message="State snapshot test",
        include_state=True,
    )

    state = State(
        {
            "inputs": {"param1": "value1", "param2": "value2"},
            "results": {"data": {"nested": "value"}},
        }
    )
    payload = (await node(state, RunnableConfig()))["results"]["debug"]

    assert "state" in payload
    assert payload["state"]["inputs"] == {"param1": "value1", "param2": "value2"}
    assert payload["state"]["results"]["data"]["nested"] == "value"


@pytest.mark.asyncio
async def test_debug_node_normalise_state_with_non_mapping_results() -> None:
    """DebugNode should handle state with non-Mapping results."""

    node = DebugNode(
        name="debug",
        message="State snapshot with non-dict results",
        include_state=True,
    )

    # State with results as a non-Mapping type (list)
    state = State(
        {
            "inputs": {"param1": "value1"},
            "results": ["item1", "item2"],  # Non-Mapping
        }
    )
    payload = (await node(state, RunnableConfig()))["results"]["debug"]

    assert "state" in payload
    assert payload["state"]["inputs"] == {"param1": "value1"}
    # results should be empty dict when it's not a Mapping in _normalise_state_snapshot
    assert payload["state"]["results"] == {}


@pytest.mark.asyncio
async def test_debug_node_no_message_no_tap_path() -> None:
    """DebugNode should work without message or tap_path (no logging)."""

    node = DebugNode(
        name="debug",
        message=None,
        tap_path=None,
    )

    state = State({"results": {"data": "value"}})
    payload = (await node(state, RunnableConfig()))["results"]["debug"]

    assert payload["message"] is None
    assert payload["tap_path"] is None
    assert payload["found"] is False


@pytest.mark.asyncio
async def test_python_sandbox_callable_print_collector() -> None:
    """PythonSandboxNode should handle callable _print that returns a string."""

    # This test covers lines 143-149: the elif callable branch
    # This branch is for when _print is callable but not a PrintCollector instance
    # We mock exec() to inject a callable _print into locals_namespace

    from unittest.mock import patch

    # Create a mock callable that will be in locals as _print
    class MockPrintCallable:
        def __call__(self):
            return "mocked output"

    original_exec = exec

    def mock_exec(bytecode, globals_dict, locals_dict):
        # Execute normally
        original_exec(bytecode, globals_dict, locals_dict)
        # Then inject a callable _print
        locals_dict["_print"] = MockPrintCallable()

    with patch("builtins.exec", side_effect=mock_exec):
        node = PythonSandboxNode(
            name="python_sandbox",
            source="result = 'test'",
            capture_stdout=True,
        )

        state = State({"results": {}, "inputs": {}})
        payload = (await node(state, RunnableConfig()))["results"]["python_sandbox"]

        assert payload["result"] == "test"
        assert payload["stdout"] == ["mocked output"]


@pytest.mark.asyncio
async def test_python_sandbox_callable_print_returns_non_string() -> None:
    """PythonSandboxNode should handle callable _print that returns non-string."""

    # This covers lines 143-149: callable returns non-string
    from unittest.mock import patch

    class MockPrintCallable:
        def __call__(self):
            return 42  # Non-string

    original_exec = exec

    def mock_exec(bytecode, globals_dict, locals_dict):
        original_exec(bytecode, globals_dict, locals_dict)
        locals_dict["_print"] = MockPrintCallable()

    with patch("builtins.exec", side_effect=mock_exec):
        node = PythonSandboxNode(
            name="python_sandbox",
            source="result = 'test'",
            capture_stdout=True,
        )

        state = State({"results": {}, "inputs": {}})
        payload = (await node(state, RunnableConfig()))["results"]["python_sandbox"]

        assert payload["result"] == "test"
        # Non-string return means stdout stays empty
        assert payload["stdout"] == []


@pytest.mark.asyncio
async def test_python_sandbox_callable_print_raises_type_error() -> None:
    """PythonSandboxNode should handle callable _print that raises TypeError."""

    # This covers lines 143-149: callable raises TypeError
    from unittest.mock import patch

    class MockPrintCallable:
        def __call__(self, required_arg):  # Requires arg, will raise TypeError
            return "output"

    original_exec = exec

    def mock_exec(bytecode, globals_dict, locals_dict):
        original_exec(bytecode, globals_dict, locals_dict)
        locals_dict["_print"] = MockPrintCallable()

    with patch("builtins.exec", side_effect=mock_exec):
        node = PythonSandboxNode(
            name="python_sandbox",
            source="result = 'test'",
            capture_stdout=True,
        )

        state = State({"results": {}, "inputs": {}})
        payload = (await node(state, RunnableConfig()))["results"]["python_sandbox"]

        assert payload["result"] == "test"
        # TypeError means stdout_value is None, so stdout stays empty
        assert payload["stdout"] == []


@pytest.mark.asyncio
async def test_sub_workflow_node_propagate_replaces_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SubWorkflowNode should replace parent results when not a Mapping."""

    # This test covers line 370: state["results"] = sub_state["results"]
    # Line 370 is defensive code that's hard to reach naturally because
    # line 334 would fail if parent results were non-Mapping.
    # We use monkeypatching to test this edge case.

    import copy

    original_deepcopy = copy.deepcopy

    def mock_deepcopy(obj):
        # Return empty dict when copying non-Mapping results
        # This simulates sub_state having valid dict results
        # despite parent having non-Mapping
        if obj == "not_a_dict":
            return {}
        return original_deepcopy(obj)

    monkeypatch.setattr("copy.deepcopy", mock_deepcopy)

    node = SubWorkflowNode(
        name="sub",
        steps=[
            {
                "type": "SetVariableNode",
                "name": "step1",
                "variables": {"value": 42},
            },
        ],
        propagate_to_parent=True,
    )

    # Set parent results to non-Mapping - line 366's setdefault will return it
    state = State({"results": "not_a_dict"})

    await node(state, RunnableConfig())

    # Line 370 should have replaced the non-Mapping with sub_state results
    assert isinstance(state["results"], dict)
    assert state["results"]["step1"] == {"value": 42}
