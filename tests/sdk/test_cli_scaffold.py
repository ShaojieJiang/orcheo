"""Tests for the plugin scaffolding module."""

from __future__ import annotations
from pathlib import Path
import pytest
from orcheo_sdk.cli.scaffold import (
    scaffold_plugin,
    validate_plugin_name,
)


# ---------------------------------------------------------------------------
# validate_plugin_name
# ---------------------------------------------------------------------------


class TestValidatePluginName:
    """Tests for validate_plugin_name."""

    def test_valid_simple_name(self) -> None:
        assert validate_plugin_name("acme") is None

    def test_valid_hyphenated_name(self) -> None:
        assert validate_plugin_name("my-plugin") is None

    def test_valid_with_digits(self) -> None:
        assert validate_plugin_name("plugin2go") is None

    def test_valid_complex_name(self) -> None:
        assert validate_plugin_name("my-cool-plugin-3") is None

    def test_empty_name(self) -> None:
        error = validate_plugin_name("")
        assert error is not None
        assert "empty" in error.lower()

    def test_uppercase_rejected(self) -> None:
        error = validate_plugin_name("MyPlugin")
        assert error is not None
        assert "Invalid" in error

    def test_starts_with_digit_rejected(self) -> None:
        error = validate_plugin_name("1plugin")
        assert error is not None
        assert "Invalid" in error

    def test_underscore_rejected(self) -> None:
        error = validate_plugin_name("my_plugin")
        assert error is not None
        assert "Invalid" in error

    def test_starts_with_hyphen_rejected(self) -> None:
        error = validate_plugin_name("-plugin")
        assert error is not None
        assert "Invalid" in error

    def test_trailing_hyphen_rejected(self) -> None:
        error = validate_plugin_name("plugin-")
        assert error is not None
        assert "Invalid" in error

    def test_double_hyphen_rejected(self) -> None:
        error = validate_plugin_name("my--plugin")
        assert error is not None
        assert "Invalid" in error


# ---------------------------------------------------------------------------
# scaffold_plugin
# ---------------------------------------------------------------------------


class TestScaffoldPlugin:
    """Tests for scaffold_plugin."""

    def test_creates_package_skeleton(self, tmp_path: Path) -> None:
        root = scaffold_plugin("hello", target_dir=tmp_path)
        assert root == tmp_path / "orcheo-plugin-hello"
        assert root.is_dir()
        assert (root / "pyproject.toml").is_file()
        assert (root / "README.md").is_file()
        assert (root / ".gitignore").is_file()
        assert (root / "src" / "orcheo_plugin_hello" / "__init__.py").is_file()
        assert (root / "src" / "orcheo_plugin_hello" / "orcheo_plugin.toml").is_file()
        assert (root / "tests" / "__init__.py").is_file()
        assert (root / "tests" / "test_plugin.py").is_file()

    def test_pyproject_contains_correct_name(self, tmp_path: Path) -> None:
        root = scaffold_plugin("hello", target_dir=tmp_path)
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
        assert 'name = "orcheo-plugin-hello"' in pyproject
        assert 'hello = "orcheo_plugin_hello:plugin"' in pyproject

    def test_pyproject_contains_author(self, tmp_path: Path) -> None:
        root = scaffold_plugin("hello", target_dir=tmp_path, author="Jane Doe")
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
        assert "Jane Doe" in pyproject

    def test_manifest_contains_exports(self, tmp_path: Path) -> None:
        root = scaffold_plugin("hello", target_dir=tmp_path, exports=["nodes", "edges"])
        manifest = (
            root / "src" / "orcheo_plugin_hello" / "orcheo_plugin.toml"
        ).read_text(encoding="utf-8")
        assert '"nodes"' in manifest
        assert '"edges"' in manifest

    def test_init_contains_pascal_case_class(self, tmp_path: Path) -> None:
        root = scaffold_plugin("my-plugin", target_dir=tmp_path)
        init_py = (root / "src" / "orcheo_plugin_my_plugin" / "__init__.py").read_text(
            encoding="utf-8"
        )
        assert "class MyPluginNode" in init_py
        assert "class MyPluginPlugin" in init_py
        assert "plugin = MyPluginPlugin()" in init_py

    def test_test_file_contains_correct_imports(self, tmp_path: Path) -> None:
        root = scaffold_plugin("my-plugin", target_dir=tmp_path)
        test_py = (root / "tests" / "test_plugin.py").read_text(encoding="utf-8")
        assert "from orcheo_plugin_my_plugin import" in test_py
        assert "MyPluginNode" in test_py
        assert "MyPluginPlugin" in test_py

    def test_readme_contains_name(self, tmp_path: Path) -> None:
        root = scaffold_plugin("hello", target_dir=tmp_path)
        readme = (root / "README.md").read_text(encoding="utf-8")
        assert "orcheo-plugin-hello" in readme

    def test_custom_description(self, tmp_path: Path) -> None:
        root = scaffold_plugin(
            "hello", target_dir=tmp_path, description="A custom desc"
        )
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
        assert "A custom desc" in pyproject
        readme = (root / "README.md").read_text(encoding="utf-8")
        assert "A custom desc" in readme

    def test_default_description(self, tmp_path: Path) -> None:
        root = scaffold_plugin("hello", target_dir=tmp_path)
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
        assert "Orcheo plugin: orcheo-plugin-hello" in pyproject

    def test_default_exports(self, tmp_path: Path) -> None:
        root = scaffold_plugin("hello", target_dir=tmp_path)
        manifest = (
            root / "src" / "orcheo_plugin_hello" / "orcheo_plugin.toml"
        ).read_text(encoding="utf-8")
        assert '"nodes"' in manifest

    def test_duplicate_directory_raises(self, tmp_path: Path) -> None:
        scaffold_plugin("hello", target_dir=tmp_path)
        with pytest.raises(FileExistsError, match="already exists"):
            scaffold_plugin("hello", target_dir=tmp_path)

    def test_invalid_name_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Invalid"):
            scaffold_plugin("Bad-Name", target_dir=tmp_path)

    def test_empty_name_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="empty"):
            scaffold_plugin("", target_dir=tmp_path)

    def test_defaults_to_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        root = scaffold_plugin("hello")
        assert root == tmp_path / "orcheo-plugin-hello"
        assert root.is_dir()

    def test_gitignore_content(self, tmp_path: Path) -> None:
        root = scaffold_plugin("hello", target_dir=tmp_path)
        gitignore = (root / ".gitignore").read_text(encoding="utf-8")
        assert "__pycache__/" in gitignore
        assert "*.egg-info/" in gitignore

    def test_hyphenated_name_to_pascal_case(self, tmp_path: Path) -> None:
        root = scaffold_plugin("foo-bar-baz", target_dir=tmp_path)
        init_py = (
            root / "src" / "orcheo_plugin_foo_bar_baz" / "__init__.py"
        ).read_text(encoding="utf-8")
        assert "class FooBarBazNode" in init_py
        assert "class FooBarBazPlugin" in init_py
