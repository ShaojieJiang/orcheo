"""Sandbox helpers tests."""

from __future__ import annotations
import ast
import sys
from types import SimpleNamespace
import pytest
from orcheo.graph.ingestion import sandbox


def test_resolve_compiler_prefers_ingestion_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_resolve_compiler should use a patched ingestion module compiler."""

    def fake_compiler(source: str, filename: str, mode: str):
        return ("compiled", source, filename, mode)

    monkeypatch.setitem(
        sys.modules,
        "orcheo.graph.ingestion",
        SimpleNamespace(compile_restricted=fake_compiler),
    )

    compiler = sandbox._resolve_compiler()

    assert compiler is fake_compiler


def test_async_allowing_transformer_visit_await() -> None:
    """AsyncAllowingTransformer should allow await expressions."""
    transformer = sandbox.AsyncAllowingTransformer()

    # Create an Await node
    await_node = ast.Await(value=ast.Name(id="foo", ctx=ast.Load()))

    # Visit the node
    result = transformer.visit_Await(await_node)

    # The result should be the visited node
    assert isinstance(result, ast.Await)
