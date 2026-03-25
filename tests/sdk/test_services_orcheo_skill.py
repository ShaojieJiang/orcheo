"""Unit tests for the Orcheo skill service helpers."""

from __future__ import annotations
import io
import tarfile as tarmod
from pathlib import Path
import pytest
from orcheo.skills.manager import SkillError
from orcheo.skills.models import (
    SkillMetadata,
    SkillValidationError,
    SkillValidationResult,
)
from orcheo_sdk.services.orcheo_skill import (
    OrcheoSkillTarget,
    _extract_downloaded_skill,
    _resolve_official_orcheo_skill_source,
    _supported_targets,
    _validate_orcheo_skill,
    install_orcheo_skill_data,
    resolve_orcheo_skill_targets,
    uninstall_orcheo_skill_data,
    update_orcheo_skill_data,
)


def _make_tar_gz(
    archive_path: Path,
    entries: list[tuple[str, bytes]],
    *,
    symlinks: list[tuple[str, str]] | None = None,
    hardlinks: list[tuple[str, str]] | None = None,
) -> Path:
    """Create a tar.gz archive with the given file entries and optional links."""
    with tarmod.open(archive_path, mode="w:gz") as archive:
        for name, content in entries:
            info = tarmod.TarInfo(name=name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
        for name, linkname in symlinks or []:
            info = tarmod.TarInfo(name=name)
            info.type = tarmod.SYMTYPE
            info.linkname = linkname
            archive.addfile(info)
        for name, linkname in hardlinks or []:
            info = tarmod.TarInfo(name=name)
            info.type = tarmod.LNKTYPE
            info.linkname = linkname
            archive.addfile(info)
    return archive_path


def _fake_supported_targets(root: Path) -> dict[str, OrcheoSkillTarget]:
    return {
        name: OrcheoSkillTarget(name=name, path=root / name)
        for name in ("claude", "codex")
    }


def _fake_validation(valid: bool, name: str | None = None) -> SkillValidationResult:
    metadata = (
        SkillMetadata(name=name or "orcheo", description="desc")
        if name is not None
        else None
    )
    errors = [] if valid else [SkillValidationError(field="path", message="oops")]
    return SkillValidationResult(valid=valid, errors=errors, skill_metadata=metadata)


def test_resolve_orcheo_skill_targets_normalizes_choices(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill._supported_targets",
        lambda: _fake_supported_targets(tmp_path),
    )

    targets = resolve_orcheo_skill_targets(("all", "claude", "claude"))

    assert [target.name for target in targets] == ["claude", "codex"]


def test_resolve_orcheo_skill_targets_rejects_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill._supported_targets",
        lambda: _fake_supported_targets(tmp_path),
    )

    with pytest.raises(SkillError, match="Unsupported target"):
        resolve_orcheo_skill_targets(("unknown",))


def test_validate_orcheo_skill_reports_invalid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("name: orcheo", encoding="utf-8")

    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill.parse_skill_md",
        lambda path: _fake_validation(valid=False),
    )

    with pytest.raises(SkillError, match="Official Orcheo skill is invalid"):
        _validate_orcheo_skill(tmp_path)


def test_validate_orcheo_skill_rejects_non_official_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("name: other-skill", encoding="utf-8")

    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill.parse_skill_md",
        lambda path: _fake_validation(valid=True, name="other-skill"),
    )

    with pytest.raises(SkillError, match="unexpected name"):
        _validate_orcheo_skill(tmp_path)


def test_install_orcheo_skill_creates_targets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dist_dir = tmp_path / "source"
    dist_dir.mkdir()
    (dist_dir / "SKILL.md").write_text("name: orcheo", encoding="utf-8")

    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill._supported_targets",
        lambda: _fake_supported_targets(tmp_path),
    )
    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill._validate_orcheo_skill",
        lambda path: None,
    )

    result = install_orcheo_skill_data(targets=("claude",), source=str(dist_dir))

    assert result["targets"][0]["status"] == "installed"
    assert (tmp_path / "claude").exists()


def test_update_orcheo_skill_marks_existing_install(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dist_dir = tmp_path / "source"
    dist_dir.mkdir()
    (dist_dir / "SKILL.md").write_text("name: orcheo", encoding="utf-8")

    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill._supported_targets",
        lambda: _fake_supported_targets(tmp_path),
    )
    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill._validate_orcheo_skill",
        lambda path: None,
    )

    target_path = tmp_path / "claude"
    target_path.mkdir(parents=True)
    _ = target_path / "existing"
    _.write_text("old", encoding="utf-8")

    result = update_orcheo_skill_data(targets=("claude",), source=str(dist_dir))

    assert result["targets"][0]["status"] == "updated"


def test_uninstall_orcheo_skill_reports_statuses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill._supported_targets",
        lambda: _fake_supported_targets(tmp_path),
    )

    installed = tmp_path / "claude"
    installed.mkdir(parents=True)
    (installed / "SKILL.md").write_text("name: orcheo", encoding="utf-8")

    result = uninstall_orcheo_skill_data(targets=("claude", "codex"))

    statuses = {entry["target"]: entry["status"] for entry in result["targets"]}
    assert statuses["claude"] == "uninstalled"
    assert statuses["codex"] == "not_installed"


def test_supported_targets_returns_claude_and_codex() -> None:
    """_supported_targets() returns both supported targets (lines 30-31)."""
    targets = _supported_targets()

    assert "claude" in targets
    assert "codex" in targets
    assert targets["claude"].name == "claude"
    assert targets["codex"].name == "codex"


def test_resolve_orcheo_skill_targets_handles_empty_truthy_iterable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Empty-but-truthy iterable falls back to all targets via guard on line 50."""
    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill._supported_targets",
        lambda: _fake_supported_targets(tmp_path),
    )

    targets = resolve_orcheo_skill_targets(iter([]))  # type: ignore[arg-type]

    assert {t.name for t in targets} == {"claude", "codex"}


def test_resolve_orcheo_skill_targets_deduplicates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Duplicate target names in input are deduplicated (line 62)."""
    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill._supported_targets",
        lambda: _fake_supported_targets(tmp_path),
    )

    targets = resolve_orcheo_skill_targets(("claude", "claude"))

    assert [t.name for t in targets] == ["claude"]


def test_validate_orcheo_skill_succeeds_with_correct_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """_validate_orcheo_skill returns normally when name matches (line 75 false branch)."""  # noqa: E501
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("name: orcheo", encoding="utf-8")

    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill.parse_skill_md",
        lambda path: _fake_validation(valid=True, name="orcheo"),
    )

    _validate_orcheo_skill(tmp_path)  # must not raise


def test_extract_downloaded_skill_returns_source_dir_on_success(
    tmp_path: Path,
) -> None:
    """Successfully extracted archive with SKILL.md returns the skill dir (line 109)."""
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()
    archive_path = _make_tar_gz(
        tmp_path / "archive.tar.gz",
        [("skill-main/SKILL.md", b"name: orcheo"), ("skill-main/README.md", b"hello")],
    )

    result = _extract_downloaded_skill(archive_path, extract_dir)

    assert result.name == "skill-main"
    assert (result / "SKILL.md").exists()


def test_extract_downloaded_skill_rejects_path_traversal(tmp_path: Path) -> None:
    """Archive entries that escape the destination root raise SkillError (line 91-93)."""  # noqa: E501
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()
    archive_path = _make_tar_gz(
        tmp_path / "archive.tar.gz", [("../outside.txt", b"evil")]
    )

    with pytest.raises(SkillError, match="invalid path"):
        _extract_downloaded_skill(archive_path, extract_dir)


def test_extract_downloaded_skill_rejects_symlinks(tmp_path: Path) -> None:
    """Archive symlinks raise SkillError (lines 94-97)."""
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()
    archive_path = _make_tar_gz(
        tmp_path / "archive.tar.gz",
        [],
        symlinks=[("skill-main/link", "/etc/passwd")],
    )

    with pytest.raises(SkillError, match="unsupported links"):
        _extract_downloaded_skill(archive_path, extract_dir)


def test_extract_downloaded_skill_rejects_hardlinks(tmp_path: Path) -> None:
    """Archive hardlinks raise SkillError (lines 94-97)."""
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()
    archive_path = _make_tar_gz(
        tmp_path / "archive.tar.gz",
        [],
        hardlinks=[("skill-main/link", "skill-main/other")],
    )

    with pytest.raises(SkillError, match="unsupported links"):
        _extract_downloaded_skill(archive_path, extract_dir)


def test_extract_downloaded_skill_rejects_multiple_dirs(tmp_path: Path) -> None:
    """Archive with multiple top-level dirs raises SkillError (lines 102-103)."""
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()
    archive_path = _make_tar_gz(
        tmp_path / "archive.tar.gz",
        [("dir1/file.txt", b"content"), ("dir2/file.txt", b"content")],
    )

    with pytest.raises(SkillError, match="unexpected layout"):
        _extract_downloaded_skill(archive_path, extract_dir)


def test_extract_downloaded_skill_rejects_missing_skill_md(tmp_path: Path) -> None:
    """Archive without SKILL.md raises SkillError (lines 107-108)."""
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()
    archive_path = _make_tar_gz(
        tmp_path / "archive.tar.gz", [("skill-main/other.txt", b"content")]
    )

    with pytest.raises(SkillError, match="missing SKILL.md"):
        _extract_downloaded_skill(archive_path, extract_dir)


def test_resolve_official_source_rejects_non_directory(tmp_path: Path) -> None:
    """A source path that is a file (not dir) raises SkillError (line 116)."""
    source_file = tmp_path / "source.txt"
    source_file.write_text("not a directory", encoding="utf-8")

    with pytest.raises(SkillError, match="is not a directory"):
        _resolve_official_orcheo_skill_source(source=str(source_file))


def test_resolve_official_source_raises_on_http_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """HTTP failure during download raises SkillError (lines 138-142)."""
    import httpx

    temp_dir = tmp_path / "orcheo-temp"
    temp_dir.mkdir()

    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill.tempfile.mkdtemp",
        lambda prefix="": str(temp_dir),
    )

    class _FailingCM:
        def __enter__(self) -> None:
            raise httpx.ConnectError("connection refused")

        def __exit__(self, *args: object) -> None:
            pass

    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill.httpx.stream",
        lambda *a, **kw: _FailingCM(),
    )

    with pytest.raises(SkillError, match="Failed to download"):
        _resolve_official_orcheo_skill_source(source=None)


def test_resolve_official_source_downloads_archive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Happy-path download extracts and validates the skill (lines 120-137)."""
    temp_dir = tmp_path / "orcheo-temp"
    temp_dir.mkdir()
    skill_dir = temp_dir / "orcheo-skill-main"
    skill_dir.mkdir()

    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill.tempfile.mkdtemp",
        lambda prefix="": str(temp_dir),
    )

    class _FakeResponse:
        def raise_for_status(self) -> None:
            pass

        def iter_bytes(self) -> list[bytes]:
            return [b""]

    class _FakeCM:
        def __enter__(self) -> _FakeResponse:
            return _FakeResponse()

        def __exit__(self, *args: object) -> None:
            pass

    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill.httpx.stream",
        lambda *a, **kw: _FakeCM(),
    )
    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill._extract_downloaded_skill",
        lambda archive, root: skill_dir,
    )
    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill._validate_orcheo_skill",
        lambda path: None,
    )

    result = _resolve_official_orcheo_skill_source(source=None)

    assert result == skill_dir


def test_install_raises_when_target_already_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """install raises SkillError when skill is already installed (lines 182-183)."""
    dist_dir = tmp_path / "source"
    dist_dir.mkdir()

    claude_path = tmp_path / "claude"
    claude_path.mkdir()  # simulate already installed

    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill._supported_targets",
        lambda: _fake_supported_targets(tmp_path),
    )
    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill._validate_orcheo_skill",
        lambda path: None,
    )

    with pytest.raises(SkillError, match="already installed"):
        install_orcheo_skill_data(targets=("claude",), source=str(dist_dir))


def test_install_cleans_up_temp_root_when_source_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """install removes the temp download root when source=None (line 205)."""
    temp_root = tmp_path / "orcheo-temp"
    source_dir = temp_root / "orcheo-skill-main"
    source_dir.mkdir(parents=True)

    target_root = tmp_path / "targets"
    target_root.mkdir()

    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill._supported_targets",
        lambda: {
            "claude": OrcheoSkillTarget(name="claude", path=target_root / "claude")
        },
    )
    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill._resolve_official_orcheo_skill_source",
        lambda source: source_dir,
    )

    result = install_orcheo_skill_data(targets=("claude",), source=None)

    assert result["action"] == "install"
    assert not temp_root.exists()


def test_update_cleans_up_temp_root_when_source_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """update removes the temp download root when source=None (line 237)."""
    temp_root = tmp_path / "orcheo-temp"
    source_dir = temp_root / "orcheo-skill-main"
    source_dir.mkdir(parents=True)

    target_root = tmp_path / "targets"
    target_root.mkdir()

    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill._supported_targets",
        lambda: {
            "claude": OrcheoSkillTarget(name="claude", path=target_root / "claude")
        },
    )
    monkeypatch.setattr(
        "orcheo_sdk.services.orcheo_skill._resolve_official_orcheo_skill_source",
        lambda source: source_dir,
    )

    result = update_orcheo_skill_data(targets=("claude",), source=None)

    assert result["action"] == "update"
    assert not temp_root.exists()
