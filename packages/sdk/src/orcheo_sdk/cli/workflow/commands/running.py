"""Run workflow command."""

from __future__ import annotations
import asyncio
import typer
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.output import render_json
from orcheo_sdk.cli.workflow.app import (
    ActorOption,
    EvaluationFileOption,
    EvaluationOption,
    InputsFileOption,
    InputsOption,
    RunnableConfigFileOption,
    RunnableConfigOption,
    WorkflowIdArgument,
    _state,
    workflow_app,
)
from orcheo_sdk.cli.workflow.inputs import (
    _resolve_evaluation_payload,
    _resolve_run_inputs,
    _resolve_runnable_config,
)
from orcheo_sdk.services import run_workflow_data


@workflow_app.command("run")
def run_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    triggered_by: ActorOption = "cli",
    inputs: InputsOption = None,
    inputs_file: InputsFileOption = None,
    config: RunnableConfigOption = None,
    config_file: RunnableConfigFileOption = None,
    verbose: bool = typer.Option(
        False,
        "--verbose/--no-verbose",
        help="Print full results payloads in streaming output.",
    ),
    stream: bool = typer.Option(
        True,
        "--stream/--no-stream",
        help="Stream node outputs in real-time (default: True).",
    ),
) -> None:
    """Trigger a workflow run using the latest version."""
    state = _state(ctx)
    state.verbose_results = verbose
    if state.settings.offline:
        raise CLIError("Workflow executions require network connectivity.")
    input_payload = _resolve_run_inputs(inputs, inputs_file)
    runnable_config = _resolve_runnable_config(config, config_file)
    from orcheo_sdk.cli import workflow as workflow_module

    graph_payload = (
        workflow_module._prepare_streaming_graph(state, workflow_id) if stream else None
    )

    if graph_payload is not None:
        graph_config, stored_runnable_config = graph_payload
        final_status = asyncio.run(
            workflow_module._stream_workflow_run(
                state,
                workflow_id,
                graph_config,
                input_payload,
                triggered_by=triggered_by,
                runnable_config=runnable_config,
                stored_runnable_config=stored_runnable_config,
            )
        )
        if final_status in {"error", "cancelled", "connection_error", "timeout"}:
            raise CLIError(f"Workflow execution failed with status: {final_status}")
        return

    result = run_workflow_data(
        state.client,
        workflow_id,
        state.settings.service_token,
        inputs=input_payload,
        triggered_by=triggered_by,
        runnable_config=runnable_config,
    )
    render_json(state.console, result, title="Run created")


@workflow_app.command("evaluate")
def evaluate_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    triggered_by: ActorOption = "cli",
    inputs: InputsOption = None,
    inputs_file: InputsFileOption = None,
    config: RunnableConfigOption = None,
    config_file: RunnableConfigFileOption = None,
    evaluation: EvaluationOption = None,
    evaluation_file: EvaluationFileOption = None,
    verbose: bool = typer.Option(
        False,
        "--verbose/--no-verbose",
        help="Print full results payloads in streaming output.",
    ),
    stream: bool = typer.Option(
        True,
        "--stream/--no-stream",
        help="Stream evaluation progress in real-time (default: True).",
    ),
) -> None:
    """Trigger an evaluation run using Agentensor evaluation mode."""
    state = _state(ctx)
    state.verbose_results = verbose
    if state.settings.offline:
        raise CLIError("Workflow evaluations require network connectivity.")
    input_payload = _resolve_run_inputs(inputs, inputs_file)
    runnable_config = _resolve_runnable_config(config, config_file)
    evaluation_payload = _resolve_evaluation_payload(evaluation, evaluation_file)
    from orcheo_sdk.cli import workflow as workflow_module

    graph_payload = (
        workflow_module._prepare_streaming_graph(state, workflow_id) if stream else None
    )
    if graph_payload is None:
        raise CLIError(
            "Evaluation requires streaming mode; unable to load workflow graph."
        )
    graph_config, stored_runnable_config = graph_payload

    final_status = asyncio.run(
        workflow_module._stream_workflow_evaluation(
            state,
            workflow_id,
            graph_config,
            input_payload,
            evaluation_payload,
            triggered_by=triggered_by,
            runnable_config=runnable_config,
            stored_runnable_config=stored_runnable_config,
        )
    )
    if final_status in {"error", "cancelled", "connection_error", "timeout"}:
        raise CLIError(f"Workflow evaluation failed with status: {final_status}")


__all__ = ["run_workflow"]
