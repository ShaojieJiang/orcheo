"""Module class."""

from abc import ABC, abstractmethod
from typing import Any
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, ConfigDict
from pydantic_ai.exceptions import UnexpectedModelBehavior
from agentensor.tensor import TextTensor


CompiledGraph = CompiledStateGraph[Any, Any, Any, Any]


class AgentModule(BaseModel, ABC):
    """Agent module."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    system_prompt: TextTensor
    llm: str | BaseChatModel = "gpt-4o-mini"

    def model_post_init(self, __context: Any) -> None:
        """Post initialization hook."""
        if isinstance(self.llm, str):  # pragma: no cover
            self.llm = init_chat_model(self.llm)

    def get_params(self) -> list[TextTensor]:
        """Get the parameters of the module."""
        params = []
        for field_name in self.__class__.model_fields.keys():
            field = getattr(self, field_name)
            if isinstance(field, TextTensor) and field.requires_grad:
                params.append(field)
        return params

    async def __call__(self, state: dict) -> dict:
        """Run the agent node."""
        assert state["output"]
        try:
            result = await self.agent.ainvoke(
                {"messages": [HumanMessage(content=state["output"].text)]}
            )
            output = str(
                result.get("structured_response", result["messages"][-1].content)
            )  # prioritize structured response over raw response
        except UnexpectedModelBehavior:  # pragma: no cover
            output = "Error"

        output_tensor = TextTensor(
            output,
            parents=[state["output"], self.system_prompt],
            requires_grad=True,
            model=self.llm,
        )

        return {"output": output_tensor}

    @property
    @abstractmethod
    def agent(self) -> CompiledGraph:
        """Get agent instance."""
        pass  # pragma: no cover
