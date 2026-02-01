"""Conversational Search Demo 4: stateful chat with query routing."""

from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from pydantic import Field
from orcheo.edges import Switch, SwitchCase
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.conversation import (
    ConversationStateNode,
    InMemoryMemoryStore,
    MemorySummarizerNode,
    QueryClarificationNode,
    TopicShiftDetectorNode,
)
from orcheo.nodes.conversational_search.embedding_registry import (
    OPENAI_TEXT_EMBEDDING_3_SMALL,
)
from orcheo.nodes.conversational_search.generation import GroundedGeneratorNode
from orcheo.nodes.conversational_search.query_processing import (
    CoreferenceResolverNode,
    QueryClassifierNode,
    QueryRewriteNode,
)
from orcheo.nodes.conversational_search.retrieval import DenseSearchNode
from orcheo.nodes.conversational_search.vector_store import PineconeVectorStore


SKIP_USER_MESSAGE_KEY = "__demo4_skip_user_message"

DEFAULT_CONFIG: dict[str, Any] = {
    "conversation": {
        "max_turns": 20,
        "max_sessions": 8,
        "max_total_turns": 160,
    },
    "query_processing": {
        "topic_shift": {
            "similarity_threshold": 0.4,
            "recent_turns": 3,
        }
    },
    "retrieval": {
        "top_k": 3,
        "score_threshold": 0.0,
    },
    "generation": {
        "citation_style": "inline",
    },
    "vector_store": {
        "type": "pinecone",
        "index_name": "orcheo-demo-dense",
        "namespace": "hybrid_search",
        "client_kwargs": {
            "api_key": "[[pinecone_api_key]]",
        },
    },
}

DEFAULT_EMBEDDING_METHOD = OPENAI_TEXT_EMBEDDING_3_SMALL


def build_vector_store_from_config(cfg: dict[str, Any]) -> PineconeVectorStore:
    """Create a Pinecone vector store using the provided demo configuration."""
    index_name = cfg.get("index_name")
    if not index_name:
        raise ValueError("Vector store config must include 'index_name'")
    client_kwargs = dict(cfg.get("client_kwargs") or {})
    return PineconeVectorStore(
        index_name=index_name,
        namespace=cfg.get("namespace"),
        client_kwargs=client_kwargs,
    )


class ConversationContextNode(TaskNode):
    """Task node that feeds the current conversation context into downstream inputs."""

    source_result_key: str = Field(
        default="conversation_state_start",
        description="Result key holding conversation history",
    )
    history_target: str = Field(
        default="history",
        description="Input key used by query processors",
    )
    summary_target: str = Field(
        default="conversation_summary",
        description="Input key that stores a cached summary",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Copy history and optional summary into the input payload for query nodes."""
        payload = state.get("results", {}).get(self.source_result_key, {})
        history = payload.get("conversation_history") or []
        summary = payload.get("summary")
        inputs = state["inputs"]
        inputs[self.history_target] = history
        if summary is not None:
            inputs[self.summary_target] = summary
        return {
            "history_length": len(history),
            "summary_seen": summary is not None,
        }


class ResultToInputsNode(TaskNode):
    """Copy selected fields from a named result entry into the graph inputs."""

    source_result_key: str = Field(description="Result entry providing field values")
    mappings: dict[str, str] = Field(description="Map of input target -> result field")
    allow_missing: bool = Field(
        default=True,
        description="If false, missing fields raise an error",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Copy the configured mappings into `state['inputs']`."""
        payload = state.get("results", {}).get(self.source_result_key, {})
        if not isinstance(payload, dict):
            return {"copied_keys": []}
        inputs = state["inputs"]
        copied: list[str] = []
        for target_key, source_field in self.mappings.items():
            if source_field not in payload:
                if not self.allow_missing:
                    raise ValueError(
                        f"Field '{source_field}' missing from {self.source_result_key}"
                    )
                continue
            inputs[target_key] = payload[source_field]
            copied.append(target_key)
        return {"copied_keys": copied}


def merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Return a deep merge of `override` into `base`."""
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


async def build_graph(
    *,
    config: dict[str, Any] | None = None,
    vector_store: PineconeVectorStore | None = None,
    memory_store: InMemoryMemoryStore | None = None,
) -> StateGraph:
    """Build the conversational demo workflow graph."""
    merged_config = merge_dicts(DEFAULT_CONFIG, config or {})
    conversation_cfg = merged_config["conversation"]
    retrieval_cfg = merged_config["retrieval"]
    generation_cfg = merged_config["generation"]
    topic_cfg = merged_config["query_processing"]["topic_shift"]
    vector_store_cfg = merged_config["vector_store"]

    vector_store = vector_store or build_vector_store_from_config(vector_store_cfg)
    if memory_store is None:
        memory_store = InMemoryMemoryStore(
            max_sessions=conversation_cfg.get("max_sessions"),
            max_total_turns=conversation_cfg.get("max_total_turns"),
        )

    conversation_start = ConversationStateNode(
        name="conversation_state_start",
        memory_store=memory_store,
        max_turns=conversation_cfg.get("max_turns", 20),
    )
    conversation_context = ConversationContextNode(
        name="conversation_context",
        source_result_key=conversation_start.name,
    )
    classifier = QueryClassifierNode(name="query_classifier")
    coref = CoreferenceResolverNode(name="coreference_resolver")
    own_query_rewrite = QueryRewriteNode(name="query_rewrite")
    coref_sync = ResultToInputsNode(
        name="coreference_result_to_inputs",
        source_result_key=coref.name,
        mappings={"query": "query"},
    )
    rewrite_sync = ResultToInputsNode(
        name="query_rewrite_to_inputs",
        source_result_key=own_query_rewrite.name,
        mappings={"query": "query"},
    )
    dense_search = DenseSearchNode(
        name="dense_search",
        vector_store=vector_store,
        top_k=retrieval_cfg.get("top_k", 3),
        score_threshold=retrieval_cfg.get("score_threshold", 0.0),
        embedding_method=DEFAULT_EMBEDDING_METHOD,
    )
    generator = GroundedGeneratorNode(
        name="generator",
        context_result_key=dense_search.name,
        citation_style=generation_cfg.get("citation_style", "inline"),
        ai_model="openai:gpt-4o-mini",
    )
    assistant_sync = ResultToInputsNode(
        name="generator_to_inputs",
        source_result_key=generator.name,
        mappings={"assistant_message": "reply"},
    )
    conversation_update = ConversationStateNode(
        name="conversation_state_update",
        memory_store=memory_store,
        user_message_key=SKIP_USER_MESSAGE_KEY,
        assistant_message_key="assistant_message",
        max_turns=conversation_cfg.get("max_turns", 20),
    )
    topic_shift = TopicShiftDetectorNode(
        name="topic_shift",
        source_result_key=conversation_update.name,
        similarity_threshold=topic_cfg.get("similarity_threshold", 0.35),
        recent_turns=topic_cfg.get("recent_turns", 2),
    )
    clarifier = QueryClarificationNode(name="query_clarification")
    summarizer = MemorySummarizerNode(
        name="memory_summarizer",
        memory_store=memory_store,
        source_result_key=conversation_start.name,
    )

    workflow = StateGraph(State)
    for node in (
        conversation_start,
        conversation_context,
        classifier,
        coref,
        own_query_rewrite,
        coref_sync,
        rewrite_sync,
        dense_search,
        generator,
        assistant_sync,
        conversation_update,
        topic_shift,
        clarifier,
        summarizer,
    ):
        workflow.add_node(node.name, node)

    workflow.set_entry_point(conversation_start.name)
    workflow.add_edge(conversation_start.name, conversation_context.name)
    workflow.add_edge(conversation_context.name, classifier.name)

    routing_switch = Switch(
        name="query_routing",
        value="{{query_classifier.classification}}",
        case_sensitive=False,
        default_branch_key="search",
        cases=[
            SwitchCase(match="search", branch_key="search"),
            SwitchCase(match="clarification", branch_key="clarification"),
            SwitchCase(match="finalize", branch_key="finalize"),
        ],
    )

    workflow.add_conditional_edges(
        classifier.name,
        routing_switch,
        {
            "search": coref.name,
            "clarification": clarifier.name,
            "finalize": summarizer.name,
        },
    )

    workflow.add_edge(coref.name, coref_sync.name)
    workflow.add_edge(coref_sync.name, own_query_rewrite.name)
    workflow.add_edge(own_query_rewrite.name, rewrite_sync.name)
    workflow.add_edge(rewrite_sync.name, dense_search.name)
    workflow.add_edge(dense_search.name, generator.name)
    workflow.add_edge(generator.name, assistant_sync.name)
    workflow.add_edge(assistant_sync.name, conversation_update.name)
    workflow.add_edge(conversation_update.name, topic_shift.name)
    workflow.add_edge(topic_shift.name, END)

    workflow.add_edge(clarifier.name, END)
    workflow.add_edge(summarizer.name, END)

    return workflow
