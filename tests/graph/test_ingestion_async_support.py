"""Tests for async function support in LangGraph script ingestion."""

from __future__ import annotations
import pytest
from orcheo.graph.ingestion.sandbox import compile_langgraph_script


def test_compile_script_with_async_function() -> None:
    """Verify that scripts with async def functions can be compiled."""
    source = """
async def run_demo():
    print("This is an async function")
    return 42

def build_graph():
    return "graph_instance"
"""
    # Should compile without errors
    bytecode = compile_langgraph_script(source)
    assert bytecode is not None
    assert bytecode.co_name == "<module>"


def test_compile_script_with_name_main_block() -> None:
    """Verify that scripts with if __name__ == '__main__' blocks are rejected.

    RestrictedPython doesn't allow __name__ (variables starting with _).
    This is expected - such blocks wouldn't execute during upload anyway
    since __name__ is set to '__orcheo_ingest__' in the sandbox.
    """
    source = """
import asyncio

async def run_demo():
    return "demo_result"

def build_graph():
    return "graph_instance"

if __name__ == "__main__":
    asyncio.run(run_demo())
"""
    # Should raise SyntaxError due to __name__ usage
    with pytest.raises(SyntaxError, match="__name__.*invalid variable name"):
        compile_langgraph_script(source)


def test_compile_script_with_sync_functions_still_works() -> None:
    """Verify that regular sync functions still work correctly."""
    source = """
def helper_function():
    return "helper"

def build_graph():
    helper = helper_function()
    return f"graph_with_{helper}"
"""
    # Should compile without errors
    bytecode = compile_langgraph_script(source)
    assert bytecode is not None


def test_async_function_does_not_execute_during_import() -> None:
    """Verify that async functions don't auto-execute during script load."""
    source = """
async def run_demo():
    # This should not execute
    raise RuntimeError("Async function should not execute!")

def build_graph():
    return "graph_instance"
"""
    # Compiling should not raise the RuntimeError
    bytecode = compile_langgraph_script(source)
    assert bytecode is not None

    # Executing the bytecode should also not raise (async function not called)
    namespace = {"__name__": "__test__"}
    exec(bytecode, namespace)
    assert "run_demo" in namespace
    assert "build_graph" in namespace
