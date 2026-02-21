"""Tests for CLI update reminders."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
from pathlib import Path
import pytest
from rich.console import Console
from orcheo_sdk.cli.cache import CacheManager
from orcheo_sdk.cli.http import ApiClient
from orcheo_sdk.cli.update_check import (
    evaluate_update_advice,
    maybe_print_update_notice,
    should_check,
)


def _cache(tmp_path: Path) -> CacheManager:
    return CacheManager(directory=tmp_path / "cache", ttl=timedelta(hours=24))


def test_should_check_once_per_ttl_window(tmp_path: Path) -> None:
    cache = _cache(tmp_path)
    assert should_check(cache, profile="default", api_url="http://api.test")
    assert should_check(cache, profile="other", api_url="http://other.test")


def test_should_check_false_when_recent_entry_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = _cache(tmp_path)

    monkeypatch.setenv("ORCHEO_UPDATE_CHECK_TTL_HOURS", "24")
    from orcheo_sdk.cli import update_check

    key = update_check._cache_key("default", "http://api.test")
    cache.store(key, {"checked": True})
    assert not should_check(cache, profile="default", api_url="http://api.test")


def test_evaluate_update_advice_suppresses_nonstable_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "orcheo_sdk.cli.update_check._read_cli_version", lambda: "1.0.0.dev1"
    )
    advice = evaluate_update_advice(
        {
            "cli": {"latest_version": "1.0.1"},
            "backend": {"current_version": "1.0.0", "latest_version": "1.0.1"},
        }
    )
    assert not advice.cli_update_available
    assert advice.backend_update_available


def test_evaluate_update_advice_uses_install_upgrade_for_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("orcheo_sdk.cli.update_check._read_cli_version", lambda: None)
    advice = evaluate_update_advice(
        {
            "cli": {"latest_version": None},
            "backend": {"current_version": "1.0.0", "latest_version": "1.0.1"},
        }
    )
    assert any("orcheo install upgrade" in line for line in advice.message_lines)


def test_maybe_print_update_notice_soft_fails(tmp_path: Path) -> None:
    cache = _cache(tmp_path)
    client = ApiClient(base_url="http://api.test", token="token")
    console = Console(record=True)

    def _raise(_path: str) -> dict[str, object]:
        raise RuntimeError("boom")

    client.get = _raise  # type: ignore[assignment]

    maybe_print_update_notice(
        cache=cache,
        client=client,
        profile="default",
        console=console,
    )

    output = console.export_text()
    assert "update reminder" not in output


def test_maybe_print_update_notice_prints_when_update_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = _cache(tmp_path)
    client = ApiClient(base_url="http://api.test", token="token")
    console = Console(record=True)

    monkeypatch.setattr(
        "orcheo_sdk.cli.update_check._read_cli_version", lambda: "1.0.0"
    )

    client.get = lambda _path: {  # type: ignore[assignment]
        "cli": {"latest_version": "1.0.1"},
        "backend": {"current_version": "1.0.0", "latest_version": "1.0.1"},
    }

    maybe_print_update_notice(
        cache=cache,
        client=client,
        profile="default",
        console=console,
    )

    output = console.export_text()
    assert "Orcheo update reminder" in output

    from orcheo_sdk.cli import update_check

    key = update_check._cache_key("default", "http://api.test")
    entry = cache.load(key)
    assert entry is not None
    checked_at = datetime.fromisoformat(entry.payload["checked_at"])
    assert checked_at.tzinfo == UTC
