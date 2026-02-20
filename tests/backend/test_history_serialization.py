"""Tests for history serialization helper functions."""

from __future__ import annotations
import sys
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path
from uuid import uuid4
import pytest
from orcheo_backend.app.history.serialization import (
    normalize_json_mapping,
    normalize_json_value,
)


class _Color(Enum):
    RED = "red"


@dataclass
class _Payload:
    value: int


class _ModelDumpTypeErrorThenOk:
    def __init__(self) -> None:
        self.calls = 0

    def model_dump(self, **kwargs):
        self.calls += 1
        if kwargs:
            raise TypeError("unsupported kwargs")
        return {"value": 7}


class _ModelDumpError:
    def model_dump(self, **kwargs):
        raise RuntimeError("boom")


class _ModelDumpAlwaysTypeError:
    def model_dump(self, **kwargs):
        raise TypeError("unsupported")


def test_normalize_json_mapping_wraps_non_mapping_value() -> None:
    assert normalize_json_mapping([1, 2]) == {"value": [1, 2]}


def test_normalize_json_value_handles_scalar_conversions() -> None:
    now = datetime(2024, 1, 2, 3, 4, 5)
    assert normalize_json_value(now) == now.isoformat()
    assert normalize_json_value(date(2024, 1, 2)) == "2024-01-02"
    assert normalize_json_value(time(3, 4, 5)) == "03:04:05"
    assert normalize_json_value(Decimal("1.23")) == "1.23"
    assert normalize_json_value(Path("/tmp/demo")) == "/tmp/demo"
    assert normalize_json_value(uuid4()).count("-") == 4
    assert normalize_json_value(b"\xffx") == "\ufffdx"
    assert normalize_json_value(_Color.RED) == "red"


def test_normalize_json_value_handles_recursive_values() -> None:
    recursive: list[object] = []
    recursive.append(recursive)
    assert normalize_json_value(recursive) == ["<recursive>"]


def test_normalize_json_value_handles_dataclass_and_set() -> None:
    result = normalize_json_value({"payload": _Payload(3), "ids": {2, 1}})
    assert result["payload"] == {"value": 3}
    assert sorted(result["ids"]) == [1, 2]


def test_normalize_json_value_model_dump_type_error_fallback() -> None:
    value = _ModelDumpTypeErrorThenOk()
    assert normalize_json_value(value) == {"value": 7}
    assert value.calls == 2


def test_normalize_json_value_model_dump_exception_falls_back_to_object_dict() -> None:
    class _WithDictError(_ModelDumpError):
        def __init__(self) -> None:
            self.name = "fallback"

    assert normalize_json_value(_WithDictError()) == {"name": "fallback"}


def test_normalize_json_value_object_dict_type_error_falls_back_to_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serialization_module = sys.modules[normalize_json_value.__module__]

    class _Value:
        pass

    def _raise_type_error(obj):
        if isinstance(obj, _Value):
            raise TypeError("no vars")
        return vars(obj)

    monkeypatch.setattr(serialization_module, "vars", _raise_type_error, raising=False)
    assert isinstance(normalize_json_value(_Value()), str)


def test_normalize_json_value_without_object_dict_falls_back_to_string() -> None:
    assert isinstance(normalize_json_value(object()), str)


def test_normalize_json_value_model_dump_type_error_twice_falls_back_to_string() -> (
    None
):
    assert normalize_json_value(_ModelDumpAlwaysTypeError()) == {}
