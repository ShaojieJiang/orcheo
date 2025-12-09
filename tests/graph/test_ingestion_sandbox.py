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


def test_async_allowing_transformer_visit_annassign() -> None:
    """AsyncAllowingTransformer should allow annotated assignments (PEP 526)."""
    transformer = sandbox.AsyncAllowingTransformer()

    # Create an AnnAssign node: field: int = 42
    annassign_node = ast.AnnAssign(
        target=ast.Name(id="field", ctx=ast.Store()),
        annotation=ast.Name(id="int", ctx=ast.Load()),
        value=ast.Constant(value=42),
        simple=1,
    )

    # Visit the node
    result = transformer.visit_AnnAssign(annassign_node)

    # The result should be the visited node
    assert isinstance(result, ast.AnnAssign)


def test_async_allowing_transformer_visit_name_dunder_name() -> None:
    """AsyncAllowingTransformer should allow reading __name__ special variable."""
    transformer = sandbox.AsyncAllowingTransformer()

    # Create a Name node for reading __name__
    name_node = ast.Name(id="__name__", ctx=ast.Load())

    # Visit the node
    result = transformer.visit_Name(name_node)

    # The result should be the node itself (not transformed)
    assert isinstance(result, ast.Name)
    assert result.id == "__name__"


def test_create_sandbox_namespace_allows_common_builtins() -> None:
    """Ensure restricted namespace exposes safe aggregate builtins."""
    namespace = sandbox.create_sandbox_namespace()
    safe_builtins = namespace["__builtins__"]

    assert safe_builtins["max"](1, 3) == 3
    assert safe_builtins["min"](1, 3) == 1
