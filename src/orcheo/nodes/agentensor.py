"""Agentensor evaluation/training node."""

from __future__ import annotations
import asyncio
import inspect
import logging
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, Literal, cast
from langchain_core.runnables import RunnableConfig
from pydantic import ConfigDict, Field
from orcheo.agentensor.checkpoints import (
    AgentensorCheckpoint,
    AgentensorCheckpointStore,
)
from orcheo.agentensor.evaluation import (
    EvaluationCase,
    EvaluationContext,
    EvaluationDataset,
    EvaluatorDefinition,
)
from orcheo.agentensor.prompts import TrainablePrompts, build_text_tensors
from orcheo.agentensor.training import OptimizerConfig
from orcheo.graph.ingestion import LANGGRAPH_SCRIPT_FORMAT
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


logger = logging.getLogger(__name__)


@registry.register(
    NodeMetadata(
        name="AgentensorNode",
        description=(
            "Evaluate or train agent prompts using Agentensor datasets and evaluators."
        ),
        category="agentensor",
    )
)
class AgentensorNode(TaskNode):
    """Node shell for Agentensor evaluation and training flows."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    mode: Literal["evaluate", "train"] = "evaluate"
    prompts: TrainablePrompts = Field(
        default_factory=dict,
        description="Trainable prompt definitions resolved from runnable configs.",
    )
    dataset: EvaluationDataset | None = Field(
        default=None,
        description="Dataset of cases to evaluate (optional for prompt-only runs).",
    )
    evaluators: list[EvaluatorDefinition] = Field(
        default_factory=list,
        description="Evaluators applied to each case output.",
    )
    max_cases: int | None = Field(
        default=None,
        ge=1,
        description="Optional cap on the number of cases to run.",
    )
    compiled_graph: Any | None = Field(
        default=None,
        exclude=True,
        description="Compiled LangGraph used for evaluation.",
    )
    graph_config: Mapping[str, Any] | None = Field(
        default=None,
        exclude=True,
        description="Graph config to shape evaluation state.",
    )
    state_config: Mapping[str, Any] | None = Field(
        default=None,
        exclude=True,
        description="Runnable config injected into evaluation state.",
    )
    progress_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = Field(
        default=None,
        exclude=True,
        description="Optional hook for streaming evaluation progress.",
    )
    optimizer: OptimizerConfig = Field(
        default_factory=OptimizerConfig,
        description="Training optimizer configuration when mode='train'.",
    )
    checkpoint_store: AgentensorCheckpointStore | None = Field(
        default=None,
        exclude=True,
        description="Optional persistence layer for training checkpoints.",
    )
    workflow_id: str | None = Field(
        default=None,
        description="Workflow identifier used to persist checkpoints.",
    )

    _max_concurrency_cap = 8

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute the configured evaluation or return prompt metadata."""
        resolved_prompts = {
            name: prompt.model_dump(mode="json")
            for name, prompt in self.prompts.items()
        }
        if self.state_config is None and isinstance(state, Mapping):
            maybe_config = state.get("config")
            if isinstance(maybe_config, Mapping):
                self.state_config = maybe_config
        tag_payload: list[str] | None = None
        if isinstance(config, Mapping):
            tags = config.get("tags")
            if isinstance(tags, list):
                tag_payload = [str(tag) for tag in tags]
        result_base = {
            "mode": self.mode,
            "prompts": resolved_prompts,
            "tags": tag_payload or [],
        }
        if self.mode == "train":
            return await self._run_training(state, config, result_base)
        if self.mode != "evaluate":
            return result_base
        if self.dataset is None or not self.dataset.cases:
            return result_base | {"summary": {}, "results": []}

        compiled_graph = self._require_compiled_graph()
        evaluators = self._resolve_evaluators()
        cases = list(self.dataset.cases)
        if self.max_cases is not None:
            cases = cases[: self.max_cases]
        aggregated: dict[str, list[float]] = {
            definition.id: [] for definition, _ in evaluators
        }
        case_results: list[dict[str, Any]] = []
        for index, case in enumerate(cases):
            case_inputs = self._merge_inputs(state, case)
            start = time.perf_counter()
            output_state = await compiled_graph.ainvoke(
                self._build_case_state(case_inputs),
                config=config,
            )
            duration_ms = (time.perf_counter() - start) * 1000.0
            output_payload = self._extract_output(output_state)
            context = EvaluationContext(
                inputs=case_inputs,
                output=output_payload,
                expected_output=case.expected_output,
                metadata=case.metadata,
                duration_ms=duration_ms,
            )
            evaluations = await self._evaluate_case(
                evaluators, context, aggregated=aggregated
            )
            case_result = {
                "case_index": index,
                "inputs": case_inputs,
                "output": output_payload,
                "evaluations": evaluations,
                "metadata": case.metadata,
                "duration_ms": duration_ms,
            }
            case_results.append(case_result)
            await self._emit_progress(
                {
                    "node": self.name,
                    "event": "evaluation_progress",
                    "payload": case_result,
                }
            )

        summary = self._summarize_metrics(aggregated)
        summary_payload = {
            "node": self.name,
            "event": "evaluation_summary",
            "payload": {
                "dataset_id": self.dataset.id,
                "summary": summary,
                "cases_ran": len(case_results),
            },
        }
        await self._emit_progress(summary_payload)

        return result_base | {
            "dataset_id": self.dataset.id,
            "summary": summary,
            "results": case_results,
        }

    async def _run_training(
        self,
        state: State,
        config: RunnableConfig,
        result_base: dict[str, Any],
    ) -> dict[str, Any]:
        if self.dataset is None or not self.dataset.cases:
            return result_base | {
                "summary": {},
                "results": [],
                "checkpoints": [],
            }

        trainable_prompts = [
            name
            for name, prompt in self.prompts.items()
            if getattr(prompt, "requires_grad", False)
        ]
        if not trainable_prompts:
            msg = (
                "AgentensorNode training requires at least one prompt with "
                "requires_grad=True."
            )
            raise ValueError(msg)

        compiled_graph = self._require_compiled_graph()
        evaluators = self._resolve_evaluators()
        cases = list(self.dataset.cases)
        if self.max_cases is not None:
            cases = cases[: self.max_cases]

        capped_config = self._enforce_training_limits(config)
        checkpoints: list[dict[str, Any]] = []
        best_checkpoint: AgentensorCheckpoint | None = None
        best_score: float = -1.0
        all_results: list[dict[str, Any]] = []

        for epoch in range(1, self.optimizer.epochs + 1):
            runtime_prompts = build_text_tensors(self.prompts)
            self._refresh_state_prompts(runtime_prompts)

            aggregated: dict[str, list[float]] = {
                definition.id: [] for definition, _ in evaluators
            }
            case_results = await self._run_training_cases(
                cases,
                compiled_graph,
                capped_config,
                runtime_prompts,
                evaluators,
                aggregated=aggregated,
                epoch=epoch,
                state=state,
            )
            all_results.extend(case_results)
            summary = self._summarize_metrics(aggregated)
            self._apply_optimizer(runtime_prompts)
            score = self._score_summary(summary)
            should_checkpoint = (
                epoch % max(1, self.optimizer.checkpoint_interval) == 0
                or epoch == self.optimizer.epochs
            )
            checkpoint_obj: AgentensorCheckpoint | None = None
            if should_checkpoint:
                checkpoint_obj = await self._emit_checkpoint(
                    summary,
                    capped_config,
                    epoch=epoch,
                    is_best=score >= best_score,
                )
                checkpoints.append(checkpoint_obj.model_dump(mode="json"))
                await self._emit_progress(
                    {
                        "node": self.name,
                        "event": "training_checkpoint",
                        "payload": checkpoint_obj.model_dump(mode="json"),
                    }
                )

            if score >= best_score:
                best_score = score
                if checkpoint_obj is None:
                    checkpoint_obj = await self._emit_checkpoint(
                        summary,
                        capped_config,
                        epoch=epoch,
                        is_best=True,
                    )
                    checkpoints.append(checkpoint_obj.model_dump(mode="json"))
                best_checkpoint = checkpoint_obj

            await self._emit_progress(
                {
                    "node": self.name,
                    "event": "training_epoch_complete",
                    "payload": {
                        "epoch": epoch,
                        "summary": summary,
                    },
                }
            )

        best_payload = (
            best_checkpoint.model_dump(mode="json") if best_checkpoint else None
        )
        trained_prompts = {
            name: prompt.model_dump(mode="json")
            for name, prompt in self.prompts.items()
        }
        return result_base | {
            "dataset_id": self.dataset.id,
            "summary": best_payload["metrics"] if best_payload else {},
            "results": all_results,
            "checkpoints": checkpoints,
            "best_checkpoint": best_payload,
            "prompts": trained_prompts,
        }

    async def _evaluate_case(
        self,
        evaluators: Sequence[tuple[EvaluatorDefinition, Any]],
        context: EvaluationContext,
        *,
        aggregated: dict[str, list[float]],
    ) -> dict[str, dict[str, Any]]:
        evaluations: dict[str, dict[str, Any]] = {}
        for definition, evaluator in evaluators:
            outcome = await self._run_evaluator(definition, evaluator, context)
            evaluations[definition.id] = outcome
            aggregated.setdefault(definition.id, []).append(outcome["score"])
        return evaluations

    async def _run_evaluator(
        self,
        definition: EvaluatorDefinition,
        evaluator: Any,
        context: EvaluationContext,
    ) -> dict[str, Any]:
        try:
            if hasattr(evaluator, "evaluate"):
                candidate = evaluator.evaluate(context)
            else:
                candidate = evaluator(context)
            result = await candidate if inspect.iscoroutine(candidate) else candidate
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception(
                "Evaluator %s failed while scoring case.", definition.id, exc_info=exc
            )
            return {"score": 0.0, "passed": False, "reason": str(exc)}

        return self._normalise_evaluation_result(result)

    @staticmethod
    def _normalise_evaluation_result(result: Any) -> dict[str, Any]:
        score: float | None = None
        reason: str | None = None
        value: Any = result

        if hasattr(result, "value"):
            value = result.value  # type: ignore[attr-defined]
            reason = result.reason if hasattr(result, "reason") else None
        elif isinstance(result, Mapping):
            if "value" in result:
                value = result["value"]
            reason = result.get("reason")

        if isinstance(value, bool):
            score = 1.0 if value else 0.0
            passed = value
        elif isinstance(value, int | float):
            score = float(value)
            passed = score >= 0.5
        else:
            passed = False if value is None else bool(value)

        if score is None:
            score = 1.0 if passed else 0.0
        return {"score": score, "passed": passed, "reason": reason}

    def _summarize_metrics(
        self, aggregated: Mapping[str, list[float]]
    ) -> dict[str, float]:
        summary: dict[str, float] = {}
        for evaluator_id, scores in aggregated.items():
            if scores:
                summary[evaluator_id] = sum(scores) / len(scores)
            else:
                summary[evaluator_id] = 0.0
        return summary

    async def _emit_progress(self, payload: dict[str, Any]) -> None:
        if self.progress_callback is None:
            return
        await self.progress_callback(payload)

    def _merge_inputs(self, state: State, case: EvaluationCase) -> dict[str, Any]:
        base_inputs: Mapping[str, Any] | None = None
        if isinstance(state, Mapping):
            if "inputs" in state and isinstance(state["inputs"], Mapping):
                base_inputs = state["inputs"]
            else:
                base_inputs = state
        merged: dict[str, Any] = {}
        if isinstance(base_inputs, Mapping):
            merged.update(base_inputs)
        merged.update(case.inputs)
        return merged

    def _build_case_state(self, inputs: Mapping[str, Any]) -> dict[str, Any]:
        runtime_config: Mapping[str, Any] = (
            dict(self.state_config) if isinstance(self.state_config, Mapping) else {}
        )
        if (
            self.graph_config
            and isinstance(self.graph_config, Mapping)
            and self.graph_config.get("format") == LANGGRAPH_SCRIPT_FORMAT
        ):
            state = dict(inputs)
            state["config"] = runtime_config
            return state
        return {
            "messages": [],
            "results": {},
            "inputs": dict(inputs),
            "structured_response": None,
            "config": runtime_config,
        }

    @staticmethod
    def _extract_output(output_state: Any) -> Any:
        if isinstance(output_state, Mapping):
            if "results" in output_state:
                return output_state["results"]
            if "output" in output_state:
                return output_state["output"]
        return output_state

    def _require_compiled_graph(self) -> Any:
        if self.compiled_graph is None:
            msg = "AgentensorNode evaluation requires a compiled graph."
            raise ValueError(msg)
        return self.compiled_graph

    def _enforce_training_limits(self, config: RunnableConfig) -> RunnableConfig:
        if not isinstance(config, Mapping):
            return config
        updated = dict(config)
        allowed_concurrency = min(
            self.optimizer.max_concurrency, self._max_concurrency_cap
        )
        max_concurrency = updated.get("max_concurrency")
        if not isinstance(max_concurrency, int) or (
            max_concurrency > allowed_concurrency
        ):
            updated["max_concurrency"] = allowed_concurrency
        recursion_limit = updated.get("recursion_limit")
        if not isinstance(recursion_limit, int):
            updated["recursion_limit"] = 50
        return cast(RunnableConfig, updated)

    def _resolve_evaluators(self) -> list[tuple[EvaluatorDefinition, Any]]:
        resolved: list[tuple[EvaluatorDefinition, Any]] = []
        for definition in self.evaluators:
            evaluator = definition.load()
            resolved.append((definition, evaluator))
        return resolved

    def _refresh_state_prompts(self, prompts: Mapping[str, Any]) -> None:
        if not prompts:
            return
        base_config = (
            dict(self.state_config) if isinstance(self.state_config, Mapping) else {}
        )
        base_config["prompts"] = prompts
        self.state_config = base_config

    async def _run_training_cases(
        self,
        cases: Sequence[EvaluationCase],
        compiled_graph: Any,
        config: RunnableConfig,
        runtime_prompts: Mapping[str, Any],
        evaluators: Sequence[tuple[EvaluatorDefinition, Any]],
        *,
        aggregated: dict[str, list[float]],
        epoch: int,
        state: State,
    ) -> list[dict[str, Any]]:
        case_results: list[dict[str, Any]] = []
        for index, case in enumerate(cases):
            case_inputs = self._merge_inputs(state, case)
            start = time.perf_counter()
            try:
                output_state = await asyncio.wait_for(
                    compiled_graph.ainvoke(
                        self._build_case_state(case_inputs),
                        config=config,
                    ),
                    timeout=self.optimizer.case_timeout_seconds,
                )
            except TimeoutError:
                duration_ms = (time.perf_counter() - start) * 1000.0
                case_result = {
                    "case_index": index,
                    "epoch": epoch,
                    "error": "timeout",
                    "duration_ms": duration_ms,
                    "evaluations": {},
                }
                case_results.append(case_result)
                await self._emit_progress(
                    {
                        "node": self.name,
                        "event": "training_progress",
                        "payload": case_result,
                    }
                )
                continue
            except Exception as exc:  # pragma: no cover - defensive
                duration_ms = (time.perf_counter() - start) * 1000.0
                failure_reason = str(exc)
                evaluations = {
                    definition.id: {
                        "score": 0.0,
                        "passed": False,
                        "reason": failure_reason,
                    }
                    for definition, _ in evaluators
                }
                for definition in evaluations:
                    aggregated.setdefault(definition, []).append(0.0)
                case_result = {
                    "case_index": index,
                    "epoch": epoch,
                    "error": failure_reason,
                    "duration_ms": duration_ms,
                    "evaluations": evaluations,
                }
                case_results.append(case_result)
                await self._emit_progress(
                    {
                        "node": self.name,
                        "event": "training_progress",
                        "payload": case_result,
                    }
                )
                continue

            duration_ms = (time.perf_counter() - start) * 1000.0
            output_payload = self._extract_output(output_state)
            context = EvaluationContext(
                inputs=case_inputs,
                output=output_payload,
                expected_output=case.expected_output,
                metadata=case.metadata,
                duration_ms=duration_ms,
            )
            evaluations = await self._evaluate_case(
                evaluators, context, aggregated=aggregated
            )
            self._apply_gradients(runtime_prompts, evaluations)
            case_result = {
                "case_index": index,
                "epoch": epoch,
                "inputs": case_inputs,
                "output": output_payload,
                "evaluations": evaluations,
                "metadata": case.metadata,
                "duration_ms": duration_ms,
            }
            case_results.append(case_result)
            await self._emit_progress(
                {
                    "node": self.name,
                    "event": "training_progress",
                    "payload": case_result,
                }
            )
        return case_results

    def _apply_gradients(
        self, prompts: Mapping[str, Any], evaluations: Mapping[str, Mapping[str, Any]]
    ) -> None:
        feedback: list[str] = []
        for evaluation in evaluations.values():
            if evaluation.get("passed") is True:
                continue
            reason = evaluation.get("reason")
            if reason:
                feedback.append(str(reason))
        if not feedback:
            return
        gradient = " ".join(feedback)
        for prompt in prompts.values():
            backward = getattr(prompt, "backward", None)
            if backward is None:
                continue
            backward(gradient)

    def _apply_optimizer(self, prompts: Mapping[str, Any]) -> None:
        for name, prompt in prompts.items():
            grad = getattr(prompt, "text_grad", "")
            requires_grad = getattr(prompt, "requires_grad", False)
            if not requires_grad or not grad:
                continue
            base_prompt = self.prompts.get(name)
            if base_prompt is None:
                continue
            updated_text = self._rewrite_prompt(base_prompt.text, grad)
            base_prompt.text = updated_text
            reset = getattr(prompt, "zero_grad", None)
            if reset is not None:
                reset()

    @staticmethod
    def _rewrite_prompt(text: str, grad: str) -> str:
        cleaned_grad = " ".join(str(grad).split())
        if not cleaned_grad:
            return text
        if cleaned_grad in text:
            return text
        return f"{text.strip()}\n\n[feedback] {cleaned_grad}".strip()

    def _score_summary(self, summary: Mapping[str, float]) -> float:
        if not summary:
            return 0.0
        return sum(summary.values()) / len(summary)

    async def _emit_checkpoint(
        self,
        summary: Mapping[str, float],
        config: RunnableConfig,
        *,
        epoch: int,
        is_best: bool,
    ) -> AgentensorCheckpoint:
        checkpoint_config = self._checkpoint_config(config)
        metadata = {"epoch": epoch, "summary": dict(summary)}
        if self.checkpoint_store is not None and self.workflow_id is not None:
            return await self.checkpoint_store.record_checkpoint(
                workflow_id=self.workflow_id,
                runnable_config=checkpoint_config,
                metrics=summary,
                metadata=metadata,
                is_best=is_best,
            )

        return AgentensorCheckpoint(
            workflow_id=self.workflow_id or "unknown",
            config_version=epoch,
            runnable_config=checkpoint_config,
            metrics=dict(summary),
            metadata=metadata,
            is_best=is_best,
        )

    def _checkpoint_config(self, config: RunnableConfig) -> dict[str, Any]:
        base_config = dict(config) if isinstance(config, Mapping) else {}
        if self.prompts:
            base_config["prompts"] = {
                name: prompt.model_dump(mode="json")
                for name, prompt in self.prompts.items()
            }
        return base_config


__all__ = ["AgentensorNode"]
