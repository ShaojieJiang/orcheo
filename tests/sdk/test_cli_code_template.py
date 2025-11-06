"""Code template CLI command tests."""

from __future__ import annotations
from pathlib import Path
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.main import app
from typer.testing import CliRunner


def test_code_template_creates_workflow_file(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test that code template command creates a workflow file."""
    output_file = tmp_path / "test_workflow.py"
    result = runner.invoke(
        app,
        ["code", "template", "--output", str(output_file)],
        env=env,
    )
    assert result.exit_code == 0
    assert output_file.exists()
    content = output_file.read_text()
    assert "from langgraph.graph import END, START, StateGraph" in content
    assert "def build_graph():" in content
    assert "Created workflow template" in result.stdout


def test_code_template_uses_default_filename(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test that code template uses default workflow.py filename."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(app, ["code", "template"], env=env)
        assert result.exit_code == 0
        assert Path("workflow.py").exists()
        assert "Created workflow template: workflow.py" in result.stdout


def test_code_template_prevents_overwrite_without_force(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test template prevents overwriting existing files without --force."""
    output_file = tmp_path / "existing.py"
    output_file.write_text("# existing content")

    result = runner.invoke(
        app,
        ["code", "template", "--output", str(output_file)],
        env=env,
    )
    assert result.exit_code == 1
    assert "already exists" in result.stdout
    assert "--force" in result.stdout
    # Original content should be preserved
    assert output_file.read_text() == "# existing content"


def test_code_template_overwrites_with_force(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test that template command overwrites with --force flag."""
    output_file = tmp_path / "existing.py"
    output_file.write_text("# existing content")

    result = runner.invoke(
        app,
        ["code", "template", "--output", str(output_file), "--force"],
        env=env,
    )
    assert result.exit_code == 0
    content = output_file.read_text()
    assert "# existing content" not in content
    assert "from langgraph.graph import END, START, StateGraph" in content


def test_code_template_includes_next_steps(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test that template command shows next steps to user."""
    output_file = tmp_path / "workflow.py"
    result = runner.invoke(
        app,
        ["code", "template", "--output", str(output_file)],
        env=env,
    )
    assert result.exit_code == 0
    assert "Next steps:" in result.stdout
    assert "Edit" in result.stdout
    assert "Test locally" in result.stdout
    assert "Upload to Orcheo" in result.stdout


def test_code_template_fails_when_output_is_directory(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test that template command fails when output path is a directory."""
    output_dir = tmp_path / "my_dir"
    output_dir.mkdir()

    result = runner.invoke(
        app,
        ["code", "template", "--output", str(output_dir)],
        env=env,
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "is a directory" in str(result.exception)
    assert "provide a file path" in str(result.exception)


def test_code_template_fails_when_parent_is_file(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test that template command fails when parent path is a file."""
    parent_file = tmp_path / "parent.txt"
    parent_file.write_text("I am a file")
    output_path = parent_file / "workflow.py"

    result = runner.invoke(
        app,
        ["code", "template", "--output", str(output_path)],
        env=env,
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "is not a directory" in str(result.exception)


def test_code_template_creates_parent_directories(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test that template command creates parent directories if they don't exist."""
    output_file = tmp_path / "nested" / "dirs" / "workflow.py"

    result = runner.invoke(
        app,
        ["code", "template", "--output", str(output_file)],
        env=env,
    )
    assert result.exit_code == 0
    assert output_file.exists()
    assert output_file.parent.is_dir()
    content = output_file.read_text()
    assert "from langgraph.graph import END, START, StateGraph" in content
