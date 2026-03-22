"""Plugin scaffolding — generate a new plugin package skeleton."""

from __future__ import annotations
import re
from pathlib import Path
from typing import Any


_PYPROJECT_TEMPLATE = """\
[build-system]
build-backend = "setuptools.build_meta"
requires = ["setuptools>=68", "wheel"]

[project]
authors = [{{name = "{author}"}}]
description = "{description}"
name = "orcheo-plugin-{name}"
requires-python = ">=3.12"
version = "0.1.0"

[project.entry-points."orcheo.plugins"]
{name} = "orcheo_plugin_{underscored}:plugin"

[tool.setuptools.package-data]
orcheo_plugin_{underscored} = ["orcheo_plugin.toml"]

[tool.setuptools.package-dir]
"" = "src"

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.25",
    "orcheo",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
"""

_MANIFEST_TEMPLATE = """\
plugin_api_version = 1
orcheo_version = ">=0.0.0"
exports = [{exports}]
"""

_INIT_TEMPLATE = '''\
"""Orcheo plugin: orcheo-plugin-{name}."""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata
from orcheo.plugins import PluginAPI


class {class_prefix}Node(TaskNode):
    """Starter node — replace with your own logic."""

    async def run(self, state: State, config: RunnableConfig) -> dict[str, str]:
        """Return a placeholder result."""
        del state, config
        return {{"result": "Hello from orcheo-plugin-{name}!"}}


class {class_prefix}Plugin:
    """Plugin entry point registered via the orcheo.plugins entry-point group."""

    def register(self, api: PluginAPI) -> None:
        """Register all components provided by this plugin."""
        api.register_node(
            NodeMetadata(
                name="{class_prefix}Node",
                description="{class_prefix} plugin node — replace with your own.",
                category="{name}",
            ),
            {class_prefix}Node,
        )


plugin = {class_prefix}Plugin()
'''

_TEST_TEMPLATE = '''\
"""Tests for orcheo-plugin-{name}."""

from __future__ import annotations

import pytest

from orcheo.plugins import PluginAPI
from orcheo_plugin_{underscored} import {class_prefix}Node, {class_prefix}Plugin


def test_plugin_registers_node() -> None:
    """Plugin should register {class_prefix}Node through the PluginAPI."""
    api = PluginAPI()
    {class_prefix}Plugin().register(api)
    assert "{class_prefix}Node" in api.registrations.nodes


def test_plugin_registers_correct_count() -> None:
    """Plugin should register exactly one node and nothing else."""
    api = PluginAPI()
    {class_prefix}Plugin().register(api)
    assert len(api.registrations.nodes) == 1
    assert len(api.registrations.edges) == 0
    assert len(api.registrations.agent_tools) == 0
    assert len(api.registrations.triggers) == 0
    assert len(api.registrations.listeners) == 0


@pytest.mark.asyncio()
async def test_node_returns_result() -> None:
    """{class_prefix}Node.run should return the expected output dict."""
    node = {class_prefix}Node(name="test_{underscored}")
    result = await node.run({{}}, {{}})  # type: ignore[arg-type]
    assert "result" in result
    assert isinstance(result["result"], str)
'''

_GITIGNORE_TEMPLATE = """\
__pycache__/
*.py[cod]
*.so
build/
dist/
*.egg-info/
.eggs/
.venv/
"""

_README_TEMPLATE = """\
# orcheo-plugin-{name}

{description}

## Quick start

```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest
orcheo plugin install .
orcheo plugin list
```

## Further reading

- [Plugin Tutorial](https://orcheo.readthedocs.io/plugin_tutorial/)
- [Plugin Reference](https://orcheo.readthedocs.io/custom_nodes_and_tools/)
- [CLI Reference](https://orcheo.readthedocs.io/cli_reference/)
"""

# Valid plugin name: lowercase letters, digits, hyphens; must start with a letter.
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


def validate_plugin_name(name: str) -> str | None:
    """Return an error message if *name* is not a valid plugin slug, else ``None``."""
    if not name:
        return "Plugin name must not be empty."
    if not _NAME_PATTERN.match(name):
        return (
            f"Invalid plugin name {name!r}. "
            "Use lowercase letters, digits, and hyphens (e.g. 'my-plugin')."
        )
    return None


def _to_class_prefix(name: str) -> str:
    """Convert a hyphenated slug to PascalCase (e.g. ``my-plugin`` → ``MyPlugin``)."""
    return "".join(part.capitalize() for part in name.split("-"))


def scaffold_plugin(
    name: str,
    *,
    target_dir: Path | None = None,
    author: str = "Your Name",
    description: str = "",
    exports: list[str] | None = None,
) -> Path:
    """Generate a plugin package skeleton and return the root directory path."""
    error = validate_plugin_name(name)
    if error:
        raise ValueError(error)

    underscored = name.replace("-", "_")
    class_prefix = _to_class_prefix(name)
    exports_list = exports or ["nodes"]
    description = description or f"Orcheo plugin: orcheo-plugin-{name}"

    root = (target_dir or Path.cwd()) / f"orcheo-plugin-{name}"
    if root.exists():
        raise FileExistsError(
            f"Directory {root} already exists. Remove it or choose a different name."
        )

    pkg_dir = root / "src" / f"orcheo_plugin_{underscored}"
    test_dir = root / "tests"

    pkg_dir.mkdir(parents=True)
    test_dir.mkdir(parents=True)

    fmt: dict[str, Any] = {
        "name": name,
        "underscored": underscored,
        "class_prefix": class_prefix,
        "author": author,
        "description": description,
        "exports": ", ".join(f'"{e}"' for e in exports_list),
    }

    (root / "pyproject.toml").write_text(
        _PYPROJECT_TEMPLATE.format(**fmt), encoding="utf-8"
    )
    (root / ".gitignore").write_text(_GITIGNORE_TEMPLATE, encoding="utf-8")
    (root / "README.md").write_text(_README_TEMPLATE.format(**fmt), encoding="utf-8")
    (pkg_dir / "__init__.py").write_text(_INIT_TEMPLATE.format(**fmt), encoding="utf-8")
    (pkg_dir / "orcheo_plugin.toml").write_text(
        _MANIFEST_TEMPLATE.format(**fmt), encoding="utf-8"
    )
    (test_dir / "__init__.py").write_text("", encoding="utf-8")
    (test_dir / "test_plugin.py").write_text(
        _TEST_TEMPLATE.format(**fmt), encoding="utf-8"
    )

    return root
