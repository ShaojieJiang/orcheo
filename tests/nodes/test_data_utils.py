"""Tests covering helpers inside orcheo.nodes.data."""

from __future__ import annotations
from typing import Any
import pytest
from orcheo.nodes import data as data_module


def test_split_path_raises_for_empty_values() -> None:
    """_split_path should raise an error when no segments remain."""

    with pytest.raises(ValueError):
        data_module._split_path("...")


def test_extract_value_handles_sequence_indexes() -> None:
    """_extract_value should support sequence lookups and invalid branches."""

    found, value = data_module._extract_value(["a", "b", "c"], "1")
    assert found is True and value == "b"

    found, value = data_module._extract_value(["a"], "invalid")
    assert found is False and value is None

    found, value = data_module._extract_value(["only"], "10")
    assert found is False and value is None

    found, value = data_module._extract_value(123, "field")
    assert found is False and value is None


def test_assign_path_constructs_nested_structure() -> None:
    """_assign_path should build nested dictionaries as needed."""

    target: dict[str, Any] = {}
    data_module._assign_path(target, "user.profile.name", "Ada")
    assert target == {"user": {"profile": {"name": "Ada"}}}


def test_deep_merge_combines_nested_mappings() -> None:
    """_deep_merge should merge nested dictionaries recursively."""

    base = {"alpha": 1, "nested": {"x": 1}}
    incoming = {"beta": 2, "nested": {"y": 2}}
    merged = data_module._deep_merge(base, incoming)
    assert merged == {"alpha": 1, "beta": 2, "nested": {"x": 1, "y": 2}}


def test_apply_transform_handles_unknown_key() -> None:
    """_apply_transform should return original values for unknown transforms."""

    assert data_module._apply_transform("value", "unknown") == "value"


def test_transform_length_handles_various_inputs() -> None:
    """_transform_length should support mappings and fallback to zero."""

    assert data_module._transform_length({"key": "value"}) == 1
    assert data_module._transform_length(object()) == 0


def test_transform_string_handles_none() -> None:
    """_transform_string should convert None to empty string."""

    assert data_module._transform_string(None) == ""
    assert data_module._transform_string("test") == "test"
    assert data_module._transform_string(123) == "123"
