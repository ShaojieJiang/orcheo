"""Workflow download service tests."""

from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace
import pytest
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.services.workflows import download


def test_download_workflow_data_rejects_unsupported_format() -> None:
    """Download helper rejects formats other than python."""
    workflow = {"id": "wf-1"}
    selected_version = {"id": "ver-2", "version": 2, "graph": {"nodes": []}}

    def fake_get(path: str) -> object:
        if path == "/api/workflows/wf-1":
            return workflow
        if path == "/api/workflows/wf-1/versions":
            return [selected_version]
        return selected_version

    client = SimpleNamespace(get=fake_get)

    with pytest.raises(CLIError, match="Unsupported format 'json'"):
        download.download_workflow_data(
            client,
            "wf-1",
            format_type="json",
            target_version=2,
        )


def test_download_workflow_data_wraps_output_write_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """File write errors are converted into CLIError for consistent UX."""
    workflow = {"id": "wf-1"}
    selected_version = {"id": "ver-1", "version": 1, "graph": {"nodes": []}}

    def fake_get(path: str) -> object:
        if path == "/api/workflows/wf-1":
            return workflow
        if path == "/api/workflows/wf-1/versions":
            return [selected_version]
        return selected_version

    client = SimpleNamespace(get=fake_get)

    monkeypatch.setattr(
        "orcheo_sdk.cli.workflow._format_workflow_as_python",
        lambda *_args, **_kwargs: "print('hello')\n",
    )

    def fail_write_text(_self: Path, _content: str, *, encoding: str = "utf-8") -> int:
        del encoding
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", fail_write_text)

    with pytest.raises(CLIError, match="Failed to write workflow output"):
        download.download_workflow_data(
            client,
            "wf-1",
            output_path=tmp_path / "workflow.py",
        )


def test_download_workflow_data_writes_output_file_and_returns_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When output_path is provided, helper writes content and returns status payload"""
    workflow = {"id": "wf-1"}
    selected_version = {"id": "ver-3", "version": 3, "graph": {"nodes": []}}

    def fake_get(path: str) -> object:
        if path == "/api/workflows/wf-1":
            return workflow
        if path == "/api/workflows/wf-1/versions":
            return [selected_version]
        return selected_version

    client = SimpleNamespace(get=fake_get)
    output_file = tmp_path / "workflow.py"

    monkeypatch.setattr(
        "orcheo_sdk.cli.workflow._format_workflow_as_python",
        lambda *_args, **_kwargs: "print('hello')\n",
    )

    result = download.download_workflow_data(client, "wf-1", output_path=output_file)

    assert output_file.read_text(encoding="utf-8") == "print('hello')\n"
    assert result == {
        "status": "success",
        "message": f"Workflow downloaded to '{output_file}'",
        "format": "python",
    }
