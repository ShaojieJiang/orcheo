"""Unit tests for AppSettings widget set coercion helpers."""

from orcheo.config.app_settings import AppSettings
from orcheo.config.defaults import _DEFAULTS


def test_coerce_widget_set_returns_defaults_for_invalid_inputs() -> None:
    expected = set(_DEFAULTS["CHATKIT_WIDGET_TYPES"])

    assert AppSettings._coerce_widget_set(None, "CHATKIT_WIDGET_TYPES") == expected
    assert AppSettings._coerce_widget_set(object(), "CHATKIT_WIDGET_TYPES") == expected


def test_coerce_widget_set_parses_strings_and_iterables() -> None:
    default_actions = set(_DEFAULTS["CHATKIT_WIDGET_ACTION_TYPES"])

    assert AppSettings._coerce_widget_set("custom, Card ", "CHATKIT_WIDGET_TYPES") == {
        "custom",
        "Card",
    }
    assert (
        AppSettings._coerce_widget_set("   ", "CHATKIT_WIDGET_ACTION_TYPES")
        == default_actions
    )
    assert AppSettings._coerce_widget_set(["Card", ""], "CHATKIT_WIDGET_TYPES") == {
        "Card"
    }
    assert AppSettings._coerce_widget_set(
        ("Action", " "), "CHATKIT_WIDGET_ACTION_TYPES"
    ) == {"Action"}
    assert AppSettings._coerce_widget_set(
        frozenset({"ListView"}), "CHATKIT_WIDGET_TYPES"
    ) == {"ListView"}


def test_coerce_widget_set_reverts_to_defaults_for_empty_collections() -> None:
    default = set(_DEFAULTS["CHATKIT_WIDGET_TYPES"])

    assert AppSettings._coerce_widget_set([], "CHATKIT_WIDGET_TYPES") == default
    assert AppSettings._coerce_widget_set((), "CHATKIT_WIDGET_TYPES") == default


def test_coerce_postgres_pool_int_defaults_and_valid_values() -> None:
    """Test _coerce_postgres_pool_int handles various input types."""
    # None defaults to 1
    assert AppSettings._coerce_postgres_pool_int(None) == 1
    # Integer values pass through
    assert AppSettings._coerce_postgres_pool_int(5) == 5
    # String integers are converted
    assert AppSettings._coerce_postgres_pool_int("10") == 10


def test_coerce_postgres_pool_float_defaults_and_valid_values() -> None:
    """Test _coerce_postgres_pool_float handles various input types."""
    # None defaults to 30.0
    assert AppSettings._coerce_postgres_pool_float(None) == 30.0
    # Integer values are converted to float
    assert AppSettings._coerce_postgres_pool_float(60) == 60.0
    # Float values pass through
    assert AppSettings._coerce_postgres_pool_float(45.5) == 45.5
    # String numbers are converted
    assert AppSettings._coerce_postgres_pool_float("120.5") == 120.5
