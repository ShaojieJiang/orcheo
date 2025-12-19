"""Optimizer module."""

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables import Runnable
from langgraph.graph import StateGraph
from agentensor.module import AgentModule
from agentensor.tensor import TextTensor


class Optimizer:
    """Optimizer class."""

    def __init__(
        self,
        graph: StateGraph | None = None,
        model: str | BaseChatModel = "gpt-4o-mini",
        params: list[TextTensor] | None = None,
    ) -> None:
        """Initialize the optimizer."""
        self.params: list[TextTensor] = (
            self._coerce_params(params, source="params") if params is not None else []
        )
        if graph is not None and not params:
            for node in graph.nodes.values():
                runnable = getattr(node, "runnable", None)
                module: AgentModule | None = None

                if isinstance(runnable, AgentModule):
                    module = runnable
                else:
                    function = getattr(runnable, "afunc", None)
                    if isinstance(function, AgentModule):
                        module = function
                    else:
                        bound_self = getattr(function, "__self__", None)
                        if isinstance(bound_self, AgentModule):
                            module = bound_self

                if module is not None:
                    self.params.extend(
                        self._coerce_params(
                            module.get_params(),
                            source=f"{module.__class__.__name__}.get_params()",
                        )
                    )
                    continue

                param_provider = getattr(runnable, "get_params", None)
                if callable(param_provider):
                    self.params.extend(
                        self._coerce_params(
                            param_provider(),
                            source=f"{runnable.__class__.__name__}.get_params()",
                        )
                    )
        if isinstance(model, str):
            self.model = init_chat_model(model)
        else:  # pragma: no cover
            self.model = model

    def step(self) -> None:
        """Step the optimizer."""
        for param in self.params:
            if not param.text_grad:
                continue
            param.text = self.optimize(param.text, param.text_grad)

    def zero_grad(self) -> None:
        """Zero the gradients."""
        for param in self.params:
            param.zero_grad()

    def optimize(self, text: str, grad: str) -> str:
        """Optimize the text."""
        result = self.agent.invoke(
            {"messages": [HumanMessage(content=f"Feedback: {grad}\nText: {text}")]}
        )
        return result["messages"][-1].content

    @property
    def agent(self) -> Runnable:
        """Get the agent."""
        return create_agent(
            self.model,
            tools=[],
            system_prompt="Rewrite the system prompt given the feedback.",
        )

    @staticmethod
    def _coerce_params(params: object, *, source: str) -> list[TextTensor]:
        """Normalize parameters and raise if they are incompatible."""
        if isinstance(params, TextTensor):
            return [params]
        if isinstance(params, list | tuple):
            if not params:
                return []
            invalid = [param for param in params if not isinstance(param, TextTensor)]
            if invalid:
                raise TypeError(
                    f"{source} must contain only TextTensor instances, got "
                    f"{type(invalid[0]).__name__}."
                )
            return list(params)
        raise TypeError(
            f"{source} must return a TextTensor or list of TextTensor objects."
        )
