import pytest
from langchain_core.runnables import RunnableConfig
from RestrictedPython.PrintCollector import PrintCollector
from orcheo.graph.state import State
from orcheo.nodes.python_sandbox import PythonSandboxNode


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
async def test_python_sandbox_print_collector_variants() -> None:
    """PythonSandboxNode should handle various print collector states."""

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
async def test_python_sandbox_no_print_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """PythonSandboxNode handles PrintCollector with no output."""

    original_exec = exec

    def mock_exec(bytecode, globals_dict, locals_dict):
        original_exec(bytecode, globals_dict, locals_dict)
        collector = PrintCollector()
        collector.txt = []
        locals_dict["_print"] = collector

    monkeypatch.setattr("builtins.exec", mock_exec)

    node = PythonSandboxNode(
        name="python_sandbox",
        source="result = 21 * 2",
        capture_stdout=True,
    )

    state = State({"results": {}, "inputs": {}})
    payload = (await node(state, RunnableConfig()))["results"]["python_sandbox"]

    assert payload["result"] == 42
    assert payload["stdout"] == []


@pytest.mark.asyncio
async def test_python_sandbox_callable_print_collector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PythonSandboxNode should handle callable _print returning a string."""

    original_exec = exec

    class MockPrintCallable:
        def __call__(self):
            return "mocked output"

    def mock_exec(bytecode, globals_dict, locals_dict):
        original_exec(bytecode, globals_dict, locals_dict)
        locals_dict["_print"] = MockPrintCallable()

    monkeypatch.setattr("builtins.exec", mock_exec)

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
async def test_python_sandbox_callable_print_returns_non_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PythonSandboxNode should handle callable _print returning non-string."""

    original_exec = exec

    class MockPrintCallable:
        def __call__(self):
            return 42

    def mock_exec(bytecode, globals_dict, locals_dict):
        original_exec(bytecode, globals_dict, locals_dict)
        locals_dict["_print"] = MockPrintCallable()

    monkeypatch.setattr("builtins.exec", mock_exec)

    node = PythonSandboxNode(
        name="python_sandbox",
        source="result = 'test'",
        capture_stdout=True,
    )

    state = State({"results": {}, "inputs": {}})
    payload = (await node(state, RunnableConfig()))["results"]["python_sandbox"]

    assert payload["result"] == "test"
    assert payload["stdout"] == []


@pytest.mark.asyncio
async def test_python_sandbox_callable_print_raises_type_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PythonSandboxNode should handle callable _print raising TypeError."""

    original_exec = exec

    class MockPrintCallable:
        def __call__(self, required_arg):  # pragma: no cover - signature enforcement
            return "output"

    def mock_exec(bytecode, globals_dict, locals_dict):
        original_exec(bytecode, globals_dict, locals_dict)
        locals_dict["_print"] = MockPrintCallable()

    monkeypatch.setattr("builtins.exec", mock_exec)

    node = PythonSandboxNode(
        name="python_sandbox",
        source="result = 'test'",
        capture_stdout=True,
    )

    state = State({"results": {}, "inputs": {}})
    payload = (await node(state, RunnableConfig()))["results"]["python_sandbox"]

    assert payload["result"] == "test"
    assert payload["stdout"] == []
