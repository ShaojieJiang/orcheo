"""Tests for official Orcheo skill service operations."""

from __future__ import annotations
from pathlib import Path
import pytest
from orcheo.skills.manager import SkillError
from orcheo_sdk.services.orcheo_skill import (
    install_orcheo_skill_data,
    uninstall_orcheo_skill_data,
    update_orcheo_skill_data,
)


def _create_skill_source(base: Path) -> Path:
    source = base / "orcheo"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\nname: orcheo\ndescription: Official Orcheo skill.\n---\n# Orcheo\n",
        encoding="utf-8",
    )
    return source


@pytest.fixture(autouse=True)
def patch_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)


def test_install_orcheo_skill_data_installs_multiple_targets(tmp_path: Path) -> None:
    source = _create_skill_source(tmp_path / "source")

    payload = install_orcheo_skill_data(
        targets=["claude", "codex"],
        source=str(source),
    )

    assert payload["action"] == "install"
    assert [item["target"] for item in payload["targets"]] == ["claude", "codex"]
    assert (tmp_path / ".claude" / "skills" / "orcheo" / "SKILL.md").exists()
    assert (tmp_path / ".codex" / "skills" / "orcheo" / "SKILL.md").exists()


def test_install_orcheo_skill_data_rejects_existing_install(
    tmp_path: Path,
) -> None:
    source = _create_skill_source(tmp_path / "source")
    install_orcheo_skill_data(targets=["claude"], source=str(source))

    with pytest.raises(SkillError, match="already installed"):
        install_orcheo_skill_data(targets=["claude"], source=str(source))


def test_update_orcheo_skill_data_overwrites_existing_install(tmp_path: Path) -> None:
    source = _create_skill_source(tmp_path / "source")
    install_orcheo_skill_data(targets=["claude"], source=str(source))
    installed_skill = tmp_path / ".claude" / "skills" / "orcheo" / "SKILL.md"
    installed_skill.write_text("stale", encoding="utf-8")

    payload = update_orcheo_skill_data(targets=["claude"], source=str(source))

    assert payload["targets"][0]["status"] == "updated"
    assert "Official Orcheo skill." in installed_skill.read_text(encoding="utf-8")


def test_uninstall_orcheo_skill_data_handles_missing_targets(tmp_path: Path) -> None:
    source = _create_skill_source(tmp_path / "source")
    install_orcheo_skill_data(targets=["codex"], source=str(source))

    payload = uninstall_orcheo_skill_data(targets=["claude", "codex"])

    assert payload["targets"] == [
        {
            "target": "claude",
            "path": str(tmp_path / ".claude" / "skills" / "orcheo"),
            "status": "not_installed",
        },
        {
            "target": "codex",
            "path": str(tmp_path / ".codex" / "skills" / "orcheo"),
            "status": "uninstalled",
        },
    ]
    assert not (tmp_path / ".codex" / "skills" / "orcheo").exists()
