"""Helpers for ingesting workflow definitions."""

from __future__ import annotations
import contextlib
import re
import sys
from pathlib import Path
from typing import Any
from orcheo.plugins.paths import build_storage_paths
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.state import CLIState


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _generate_slug(value: str) -> str:
    """Generate a slug-safe representation of the given value."""
    normalized = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    fallback = value.strip().lower()
    return normalized or fallback or value


def _normalize_workflow_name(name: str | None) -> str | None:
    """Normalize workflow name input and ensure it is not empty."""
    if name is None:
        return None
    normalized = name.strip()
    if not normalized:
        raise CLIError("Workflow name cannot be empty.")
    return normalized


def _plugin_site_packages() -> Path:
    """Return the managed plugin ``site-packages`` path for the active Python."""
    install_dir = Path(build_storage_paths().install_dir)
    return (
        install_dir
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )


@contextlib.contextmanager
def _managed_plugin_sys_path() -> Any:
    """Temporarily expose managed plugin packages during local script loading."""
    site_packages = _plugin_site_packages()
    path_str = str(site_packages)
    should_add = site_packages.exists() and path_str not in sys.path
    if should_add:
        sys.path.insert(0, path_str)
    try:
        yield
    finally:
        if should_add:
            with contextlib.suppress(ValueError):
                sys.path.remove(path_str)


def _upload_langgraph_script(
    state: CLIState,
    workflow_config: dict[str, Any],
    workflow_id: str | None,
    path: Path,
    name_override: str | None,
) -> dict[str, Any]:
    """Upload a LangGraph script using the ingestion API."""
    script = workflow_config["script"]
    entrypoint = workflow_config.get("entrypoint")

    derived_name = path.stem.replace("_", "-")
    workflow_name = name_override or derived_name
    workflow_slug = _generate_slug(workflow_name) if name_override else derived_name

    if workflow_id:
        try:
            workflow = state.client.get(f"/api/workflows/{workflow_id}")
        except Exception as exc:
            raise CLIError(f"Failed to fetch workflow '{workflow_id}': {exc}") from exc
        if name_override and workflow.get("name") != name_override:
            try:
                state.client.put(
                    f"/api/workflows/{workflow_id}",
                    json_body={"name": name_override},
                )
                workflow["name"] = name_override
            except Exception as exc:
                raise CLIError(
                    f"Failed to rename workflow '{workflow_id}': {exc}"
                ) from exc
    else:
        create_payload = {
            "name": workflow_name,
            "slug": workflow_slug,
            "description": f"LangGraph workflow from {path.name}",
            "tags": ["langgraph", "cli-upload"],
            "actor": "cli",
        }
        try:
            workflow = state.client.post("/api/workflows", json_body=create_payload)
            workflow_id = workflow["id"]
            state.console.print(
                f"[green]Created workflow '{workflow_id}' ({workflow_name})[/green]"
            )
        except Exception as exc:
            raise CLIError(f"Failed to create workflow: {exc}") from exc

    ingest_payload = {
        "script": script,
        "entrypoint": entrypoint,
        "metadata": {"source": "cli-upload", "filename": path.name},
        "notes": f"Uploaded from {path.name} via CLI",
        "created_by": "cli",
    }
    runnable_config = workflow_config.get("runnable_config")
    if runnable_config is not None:
        ingest_payload["runnable_config"] = runnable_config

    try:
        version = state.client.post(
            f"/api/workflows/{workflow_id}/versions/ingest",
            json_body=ingest_payload,
        )
        state.console.print(
            f"[green]Ingested LangGraph script as version {version['version']}[/green]"
        )
    except Exception as exc:
        raise CLIError(f"Failed to ingest LangGraph script: {exc}") from exc

    workflow["latest_version"] = version
    return workflow


def _strip_main_block(script: str) -> str:
    """Remove if __name__ == '__main__' blocks from Python scripts."""
    lines = script.split("\n")
    filtered_lines = []
    for line in lines:
        if line.strip().startswith('if __name__ == "__main__"'):
            break
        if line.strip().startswith("if __name__ == '__main__'"):
            break
        filtered_lines.append(line)
    return "\n".join(filtered_lines)


def _load_workflow_from_python(path: Path) -> dict[str, Any]:
    """Load a workflow from a Python file."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("workflow_module", path)
    if spec is None or spec.loader is None:
        raise CLIError(f"Failed to load Python module from '{path}'.")

    module = importlib.util.module_from_spec(spec)
    sys.modules["workflow_module"] = module
    try:
        with _managed_plugin_sys_path():
            spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover
        raise CLIError(f"Failed to execute Python file: {exc}") from exc
    finally:
        sys.modules.pop("workflow_module", None)

    if hasattr(module, "workflow"):
        workflow = module.workflow
        if not hasattr(workflow, "to_deployment_payload"):
            msg = "'workflow' variable must be an orcheo_sdk.Workflow instance."
            raise CLIError(msg)

        try:
            return workflow.to_deployment_payload()
        except Exception as exc:  # pragma: no cover
            raise CLIError(f"Failed to generate deployment payload: {exc}") from exc

    try:
        script_content = path.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover
        raise CLIError(f"Failed to read file: {exc}") from exc

    script_content = _strip_main_block(script_content)

    return {
        "_type": "langgraph_script",
        "script": script_content,
        "entrypoint": None,
    }


__all__ = [
    "_generate_slug",
    "_normalize_workflow_name",
    "_upload_langgraph_script",
    "_strip_main_block",
    "_load_workflow_from_python",
]
