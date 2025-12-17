"""Text tensor primitives."""

from __future__ import annotations
from typing import Any
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent


CompiledGraph = CompiledStateGraph[Any, Any, Any, Any]


class TextTensor:
    """A tensor that represents a text."""

    def __init__(
        self,
        text: str,
        parents: list[TextTensor] | None = None,
        requires_grad: bool = False,
        metadata: dict[str, Any] | None = None,
        model: str | BaseChatModel = "gpt-4o-mini",
    ) -> None:
        """Initialize a TextTensor."""
        self.text = text
        self.requires_grad = requires_grad
        self.gradients: list[str] = []
        self.metadata = dict(metadata) if metadata is not None else {}
        self.parents: list[TextTensor] = parents or []
        if isinstance(model, str):
            self.model = init_chat_model(model)
        else:
            self.model = model

    def backward(self, grad: str = "") -> None:
        """Backward pass for the TextTensor.

        Args:
            grad (str, optional): The gradient to backpropagate. Defaults to "".
        """
        if not grad:
            return

        if self.requires_grad:
            self.gradients.append(grad)
            for parent in self.parents:
                if not parent.requires_grad:
                    continue
                grad_to_parent = self.calc_grad(parent.text, self.text, grad)
                parent.backward(grad_to_parent)

    def calc_grad(self, input_text: str, output_text: str, grad: str) -> str:
        """Calculate the gradient for the TextTensor."""
        result = self.agent.invoke(
            {
                "messages": [
                    HumanMessage(
                        content=(
                            f"Here is the input: \n\n>{input_text}\n\nI got this "
                            f"output: \n\n>{output_text}\n\nHere is the feedback: \n\n"
                            f">{grad}\n\nHow should I improve the input to get a "
                            f"better output?"
                        )
                    )
                ]
            }
        )
        return result["messages"][-1].content

    @property
    def text_grad(self) -> str:
        """String representation of the gradients."""
        return " ".join(self.gradients)

    def zero_grad(self) -> None:
        """Zero the gradients."""
        self.gradients = []

    def __str__(self) -> str:
        """Return the text as a string."""
        return self.text

    @property
    def agent(self) -> CompiledGraph:
        """Get the agent."""
        return create_react_agent(
            self.model, tools=[], prompt="Answer the user's question."
        )
