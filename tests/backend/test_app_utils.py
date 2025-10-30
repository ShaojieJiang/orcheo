"""Tests for utility functions in the app module."""

from __future__ import annotations
from unittest.mock import patch
from orcheo_backend.app import (
    _chatkit_retention_days,
    _coerce_int,
)


def test_coerce_int_with_int() -> None:
    """_coerce_int returns the int value directly."""
    assert _coerce_int(42, 10) == 42


def test_coerce_int_with_none() -> None:
    """_coerce_int returns default for None."""
    assert _coerce_int(None, 100) == 100


def test_coerce_int_with_string() -> None:
    """_coerce_int converts valid string to int."""
    assert _coerce_int("123", 10) == 123


def test_coerce_int_with_invalid_string() -> None:
    """_coerce_int returns default for invalid string."""
    assert _coerce_int("invalid", 50) == 50


def test_coerce_int_with_object() -> None:
    """_coerce_int returns default for non-numeric object."""
    assert _coerce_int(object(), 20) == 20


def test_chatkit_retention_days_default() -> None:
    """_chatkit_retention_days returns default when not set."""
    with patch("orcheo_backend.app.get_settings") as mock_settings:
        mock_settings.return_value = {}
        result = _chatkit_retention_days()
        assert result == 30


def test_chatkit_retention_days_custom() -> None:
    """_chatkit_retention_days returns configured value."""
    with patch("orcheo_backend.app.get_settings") as mock_settings:
        mock_settings.return_value = {"CHATKIT_RETENTION_DAYS": 60}
        result = _chatkit_retention_days()
        assert result == 60


def test_chatkit_retention_days_zero_returns_default() -> None:
    """_chatkit_retention_days returns 30 for zero or negative values."""
    with patch("orcheo_backend.app.get_settings") as mock_settings:
        mock_settings.return_value = {"CHATKIT_RETENTION_DAYS": 0}
        result = _chatkit_retention_days()
        assert result == 30


def test_chatkit_retention_days_negative_returns_default() -> None:
    """_chatkit_retention_days returns 30 for negative values."""
    with patch("orcheo_backend.app.get_settings") as mock_settings:
        mock_settings.return_value = {"CHATKIT_RETENTION_DAYS": -5}
        result = _chatkit_retention_days()
        assert result == 30
