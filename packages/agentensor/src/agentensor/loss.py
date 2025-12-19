"""Loss functions."""

from dataclasses import dataclass
from typing import Any
from pydantic_ai import models
from pydantic_evals.evaluators import EvaluationReason, Evaluator, EvaluatorContext
from pydantic_evals.evaluators.llm_as_a_judge import judge_input_output, judge_output
from agentensor.tensor import TextTensor


@dataclass
class LLMTensorJudge(Evaluator[TextTensor, TextTensor, Any]):
    """LLM judge for text tensors.

    Adapted from pydantic_evals.evaluators.common.LLMJudge.
    """

    rubric: str
    model: models.Model | models.KnownModelName | None = None
    include_input: bool = True

    async def evaluate(
        self,
        ctx: EvaluatorContext[TextTensor, TextTensor, Any],
    ) -> EvaluationReason:
        """Evaluate the text tensor."""
        if self.include_input:
            grading_output = await judge_input_output(
                ctx.inputs.text, ctx.output.text, self.rubric, self.model
            )
        else:
            grading_output = await judge_output(
                ctx.output.text, self.rubric, self.model
            )
        return EvaluationReason(
            value=grading_output.pass_, reason=grading_output.reason
        )

    def build_serialization_arguments(self) -> dict[str, Any]:
        """Build serialization arguments."""
        result = super().build_serialization_arguments()
        if (model := result.get("model")) and isinstance(model, models.Model):
            result["model"] = f"{model.system}:{model.model_name}"
        return result
