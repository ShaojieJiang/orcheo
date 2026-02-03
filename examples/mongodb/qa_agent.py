"""ChatKit agent workflow.

This workflow exposes a single AgentNode suitable for ChatKit's public UI.
ChatKit sends message/history payloads; the AgentNode normalizes them into
LangChain messages and generates a reply.
"""

from collections.abc import Mapping
from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from orcheo.graph.state import State
from orcheo.nodes.ai import AgentNode
from orcheo.nodes.conversational_search import (
    OPENAI_TEXT_EMBEDDING_3_SMALL,
    TextEmbeddingNode,
)
from orcheo.nodes.logic import SetVariableNode
from orcheo.nodes.mongodb import MongoDBHybridSearchNode


class HybridSearchInput(BaseModel):
    """Input for the MongoDB hybrid search tool."""

    query: str = Field(description="User question to search for.")


class HybridSearchFormatterNode(SetVariableNode):
    """Format hybrid search results into markdown output."""

    source_result_key: str = Field(
        default="hybrid_search",
        description="Result key containing hybrid search output.",
    )
    markdown_key: str = Field(
        default="markdown",
        description="Variable name used to store markdown output.",
    )
    score_precision: int = Field(
        default=3,
        ge=0,
        le=6,
        description="Decimal precision for score rounding.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Run the formatter node."""
        results = self.extract_results(state)
        markdown = self.format_markdown(results)
        variables = dict(self.variables)
        variables[self.markdown_key] = markdown
        return self.build_payload(variables)

    def extract_results(self, state: State) -> list[dict[str, Any]]:
        """Extract hybrid search results from workflow state."""
        if not isinstance(state, Mapping):
            return []
        results = state.get("results")
        if not isinstance(results, Mapping):
            return []
        hybrid_payload = results.get(self.source_result_key)
        if not isinstance(hybrid_payload, Mapping):
            return []
        items = hybrid_payload.get("results")
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, Mapping)]

    def format_markdown(self, results: list[dict[str, Any]]) -> str:
        """Format search results as readable markdown."""
        if not results:
            return "No results found."
        lines: list[str] = ["Search results:"]
        for index, item in enumerate(results, start=1):
            raw = item.get("raw", {})
            raw_dict = raw if isinstance(raw, Mapping) else {}
            platform = raw_dict.get("platform_name") or "Unknown platform"
            reason = raw_dict.get("recommendation_reason") or "No details provided."
            score = item.get("score")
            score_text = self.format_score(score)
            url = self.extract_url(raw_dict)

            lines.append(f"{index}. {platform} (score: {score_text})")
            lines.append(f"Reason: {reason}")
            if url:
                lines.append(f"Source: {url}")
            lines.append("")

        if lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines)

    def format_score(self, score: Any) -> str:
        """Format a numeric score with configured precision."""
        if isinstance(score, int | float):
            precision = self.score_precision
            return f"{score:.{precision}f}"
        return "n/a"

    @staticmethod
    def extract_url(raw: Mapping[str, Any]) -> str | None:
        """Extract a URL from raw result data."""
        for key in ("source_url", "url", "link", "source"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def merge(base: dict[str, Any], incoming: Mapping[str, Any]) -> None:
        """Recursively merge incoming mapping into base dict."""
        for key, value in incoming.items():
            if isinstance(value, Mapping):
                existing = base.get(key)
                if isinstance(existing, dict):
                    HybridSearchFormatterNode.merge(existing, value)
                else:
                    base[key] = dict(value)
            else:
                base[key] = value

    @staticmethod
    def build_nested(path: str, value: Any) -> dict[str, Any]:
        """Build a nested dict from a dotted path and a leaf value."""
        if not path:
            msg = "target_path must be a non-empty string"
            raise ValueError(msg)

        segments = [segment.strip() for segment in path.split(".") if segment.strip()]
        if not segments:
            msg = "target_path must contain at least one segment"
            raise ValueError(msg)

        root: dict[str, Any] = {}
        cursor = root
        for segment in segments[:-1]:
            cursor = cursor.setdefault(segment, {})
        cursor[segments[-1]] = value
        return root

    @staticmethod
    def build_payload(variables: Mapping[str, Any]) -> dict[str, Any]:
        """Build a flat-or-nested payload dict from variable mappings."""
        payload: dict[str, Any] = {}
        merge = HybridSearchFormatterNode.merge
        build_nested = HybridSearchFormatterNode.build_nested

        for name, value in variables.items():
            if "." in name:
                nested = build_nested(name, value)
                merge(payload, nested)
            else:
                existing = payload.get(name)
                if isinstance(existing, dict) and isinstance(value, Mapping):
                    merge(existing, value)
                elif isinstance(value, Mapping):
                    payload[name] = dict(value)
                else:
                    payload[name] = value

        return payload


def build_hybrid_search_tool_graph() -> StateGraph:
    """Build a subworkflow used as an agent tool."""
    graph = StateGraph(State)
    graph.add_node(
        "query_embedding",
        TextEmbeddingNode(
            name="query_embedding",
            input_key="query",
            embedding_method=OPENAI_TEXT_EMBEDDING_3_SMALL,
            dense_output_key="vector",
            unwrap_single=True,
        ),
    )
    graph.add_node(
        "hybrid_search",
        MongoDBHybridSearchNode(
            name="hybrid_search",
            database="{{config.configurable.database}}",
            collection="{{config.configurable.collection}}",
            text_query="{{query}}",
            vector="{{query_embedding.vector}}",
            text_paths="{{config.configurable.text_paths}}",
            vector_path="{{config.configurable.vector_path}}",
            top_k=5,
        ),
    )
    graph.add_node(
        "format_results",
        HybridSearchFormatterNode(name="format_results"),
    )
    graph.add_edge(START, "query_embedding")
    graph.add_edge("query_embedding", "hybrid_search")
    graph.add_edge("hybrid_search", "format_results")
    graph.add_edge("format_results", END)
    return graph


async def orcheo_workflow() -> StateGraph:
    """Build the ChatKit agent workflow."""
    graph = StateGraph(State)

    agent_node = AgentNode(
        name="agent",
        ai_model="{{config.configurable.ai_model}}",
        model_kwargs={"api_key": "[[openai_api_key]]"},
        system_prompt="{{config.configurable.system_prompt}}",
        workflow_tools=[
            {
                "name": "mongodb_hybrid_search",
                "description": "Hybrid search over MongoDB Atlas data.",
                "graph": build_hybrid_search_tool_graph(),
                "args_schema": HybridSearchInput,
            }
        ],
    )

    graph.add_node("agent", agent_node)
    graph.add_edge(START, "agent")
    graph.add_edge("agent", END)
    return graph
