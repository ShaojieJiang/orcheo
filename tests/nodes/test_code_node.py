import pytest
from orcheo.graph.state import State
from orcheo.nodes.code import PythonCode


@pytest.mark.asyncio
async def test_basic_code_execution():
    state = {}
    node = PythonCode(name="python_node", code="return 3")
    output = await node(state, None)
    assert output["results"] == {"python_node": 3}


@pytest.mark.asyncio
async def test_code_without_result():
    state = {}
    node = PythonCode(name="python_node", code="x = 1; y = 2; return None")
    with pytest.raises(ValueError):
        await node(state, None)


@pytest.mark.asyncio
async def test_code_with_state():
    state = {
        "results": [
            {"x": 1, "y": 2},
            {"x": 2, "y": 3},
        ]
    }
    node = PythonCode(
        name="python_node",
        code="""
x = state["results"][-1]["x"]
y = state["results"][-1]["y"]
a = x * 2
b = y + 1
result = a + b
return result
""",
    )
    output = await node(state, None)
    assert output["results"] == {"python_node": 8}


@pytest.mark.asyncio
async def test_code_with_error():
    node = PythonCode(name="python_node", code="result = undefined_var; return result")
    state = State({})
    with pytest.raises(NameError):
        await node(state, None)


@pytest.mark.asyncio
async def test_code_with_imports():
    state = {}
    node = PythonCode(
        name="python_node",
        code="""
import math
result = math.pi
return result
""",
    )
    output = await node(state, None)
    assert output["results"] == {"python_node": 3.141592653589793}
