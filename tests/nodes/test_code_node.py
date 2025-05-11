import pytest
from aic_flow.graph.state import State
from aic_flow.nodes.code import PythonCode


@pytest.mark.asyncio
async def test_basic_code_execution():
    state = {}
    node = PythonCode("python_node", "return 3")
    output = await node(state, None)
    assert output["outputs"] == {"python_node": 3}


@pytest.mark.asyncio
async def test_code_without_result():
    state = {}
    node = PythonCode("python_node", "x = 1; y = 2; return None")
    with pytest.raises(ValueError):
        await node(state, None)


@pytest.mark.asyncio
async def test_code_with_state():
    state = {
        "outputs": [
            {"x": 1, "y": 2},
            {"x": 2, "y": 3},
        ]
    }
    node = PythonCode(
        "python_node",
        """
x = state["outputs"][-1]["x"]
y = state["outputs"][-1]["y"]
a = x * 2
b = y + 1
result = a + b
return result
""",
    )
    output = await node(state, None)
    assert output["outputs"] == {"python_node": 8}


@pytest.mark.asyncio
async def test_code_with_error():
    node = PythonCode("python_node", "result = undefined_var; return result")
    state = State({})
    with pytest.raises(NameError):
        await node(state, None)


@pytest.mark.asyncio
async def test_code_with_imports():
    state = {}
    node = PythonCode(
        "python_node",
        """
import math
result = math.pi
return result
""",
    )
    output = await node(state, None)
    assert output["outputs"] == {"python_node": 3.141592653589793}
