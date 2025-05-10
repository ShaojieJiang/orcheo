"""Tests for output handling."""

import pytest
from aic_flow.graph.output import add_outputs


def test_add_outputs_basic():
    """Test basic list concatenation."""
    left = [1, 2, 3]
    right = [4, 5, 6]
    assert add_outputs(left, right) == [1, 2, 3, 4, 5, 6]


def test_add_outputs_single_item():
    """Test adding single items."""
    left = [1, 2]
    right = 3
    assert add_outputs(left, right) == [1, 2, 3]
    assert add_outputs(right, left) == [3, 1, 2]


def test_add_outputs_empty():
    """Test handling empty lists."""
    assert add_outputs([], []) == []
    assert add_outputs([1, 2], []) == [1, 2]
    assert add_outputs([], [1, 2]) == [1, 2]


def test_add_outputs_mixed_types():
    """Test handling mixed types."""
    left = [1, "two", 3.0]
    right = [True, None]
    assert add_outputs(left, right) == [1, "two", 3.0, True, None]


def test_add_outputs_partial():
    """Test partial function application."""
    add_func = add_outputs()
    assert add_func([1, 2, 3], [4, 5]) == [1, 2, 3, 4, 5]


def test_add_outputs_invalid_args():
    """Test invalid argument handling."""
    with pytest.raises(ValueError):
        add_outputs(left=[1, 2])
    with pytest.raises(ValueError):
        add_outputs(right=[1, 2])
