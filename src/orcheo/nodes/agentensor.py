"""Agentensor evaluation/training node."""

from __future__ import annotations
import inspect
import logging
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, Literal
from langchain_core.runnables import RunnableConfig
from pydantic import ConfigDict, Field
from orcheo.agentensor.evaluation import (
    EvaluationCase,
    EvaluationContext,
    EvaluationDataset,
    EvaluatorDefinition,
)
from orcheo.agentensor.prompts import TrainablePrompts
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
        base_inputs = state.get("inputs") if isinstance(state, Mapping) else None
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

    def _resolve_evaluators(self) -> list[tuple[EvaluatorDefinition, Any]]:
        resolved: list[tuple[EvaluatorDefinition, Any]] = []
        for definition in self.evaluators:
            evaluator = definition.load()
            resolved.append((definition, evaluator))
        return resolved


__all__ = ["AgentensorNode"]
