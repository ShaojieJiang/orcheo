"""Conversational Search Demo 3: stateful chat with query routing."""

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
from orcheo.runtime.credentials import CredentialResolver, credential_resolution


SKIP_USER_MESSAGE_KEY = "__demo3_skip_user_message"

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

CONVERSATION_TURNS = [
    "How do I rotate API keys?",
    "Where do I find that setting?",
    "Could you clarify which option to focus on?",
    "What about troubleshooting slow retrieval?",
    "Thanks, that helps!",
]
SESSION_ID = "demo-3-session"

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


def print_demo_introduction(vector_store_cfg: dict[str, Any]) -> None:
    """Print vector store info for the demo."""
    print("Conversation controls:", DEFAULT_CONFIG["conversation"])
    print(
        "This demo relies on Pinecone index "
        f"{vector_store_cfg['index_name']} in namespace "
        f"{vector_store_cfg['namespace']}."
    )


def print_classification_info(branch: str, classifier: dict[str, Any]) -> None:
    """Emit classification results for the current turn."""
    print(
        " Classification:",
        branch,
        f"(confidence={classifier.get('confidence', 0):.2f})",
    )


def print_clarification_requests(clarifications: list[str]) -> None:
    """Print any clarification questions returned by the graph."""
    if not clarifications:
        return
    print(" Clarification requests:")
    for question in clarifications:
        print(f"  - {question}")


async def handle_finalize_branch(
    results: dict[str, Any], memory_store: InMemoryMemoryStore
) -> None:
    """Emit summary information and fetch the stored summary."""
    summary = results.get("memory_summarizer", {}).get("summary")
    print(" Final summary persisted:", summary)
    saved = await memory_store.get_summary(SESSION_ID)
    print(" Stored summary:", saved)


def print_search_branch_details(results: dict[str, Any]) -> None:
    """Print retrieval-related outputs for a search classification."""
    coref = results.get("coreference_resolver", {})
    if coref.get("resolved"):
        print(" Coreference resolved to:", coref.get("query"))

    rewrite = results.get("query_rewrite", {})
    if rewrite:
        used_history = rewrite.get("used_history", False)
        print(
            " Rewritten query:",
            rewrite.get("query"),
            f"(used_history={used_history})",
        )

    hits = results.get("dense_search", {}).get("results", [])
    if hits:
        print(" Retrieved passages:")
        for rank, hit in enumerate(hits[:3], start=1):
            title = hit.get("metadata", {}).get("title") or hit.get("id")
            score = hit.get("score", 0.0)
            print(f"  {rank}. {title} (score={score:.2f})")

    generator = results.get("generator", {})
    print(" Reply:", generator.get("reply", "<no reply>"))
    citations = generator.get("citations", [])
    print(" Citations:", len(citations))

    topic = results.get("topic_shift", {})
    if topic:
        route = topic.get("route")
        similarity = topic.get("similarity", 0.0) * 100
        reason = topic.get("reason")
        print(
            " Topic shift:",
            route,
            f"(similarity={similarity:.1f}%, reason={reason})",
        )


async def process_demo_turn(
    app: Any,
    memory_store: InMemoryMemoryStore,
    turn_index: int,
    message: str,
) -> None:
    """Invoke the graph for a single turn and print the outputs."""
    print(f"\n--- Turn {turn_index}: {message}")
    payload = {
        "inputs": {
            "session_id": SESSION_ID,
            "user_message": message,
            "message": message,
        }
    }
    result = await app.ainvoke(payload)  # type: ignore[arg-type]
    results = result.get("results", {})
    classifier = results.get("query_classifier", {})
    branch = classifier.get("classification", "search")
    print_classification_info(branch, classifier)

    if branch == "clarification":
        clarifications = results.get("query_clarification", {}).get(
            "clarifications", []
        )
        print_clarification_requests(clarifications)
        return

    if branch == "finalize":
        await handle_finalize_branch(results, memory_store)
        return

    print_search_branch_details(results)


async def run_demo() -> None:
    """Run the conversational demo turn loop using the compiled workflow."""
    vector_store_cfg = DEFAULT_CONFIG["vector_store"]
    vector_store = build_vector_store_from_config(vector_store_cfg)

    print_demo_introduction(vector_store_cfg)

    memory_store = InMemoryMemoryStore(
        max_sessions=DEFAULT_CONFIG["conversation"]["max_sessions"],
        max_total_turns=DEFAULT_CONFIG["conversation"]["max_total_turns"],
    )
    workflow = await build_graph(
        vector_store=vector_store,
        memory_store=memory_store,
    )
    app = workflow.compile()
    resolver = setup_credentials()

    with credential_resolution(resolver):
        for turn_index, message in enumerate(CONVERSATION_TURNS, start=1):
            await process_demo_turn(app, memory_store, turn_index, message)

    print("\nDemo complete.")


def setup_credentials() -> CredentialResolver:
    """Return the resolver that exposes the Pinecone credential."""
    from orcheo_backend.app.dependencies import get_vault

    vault = get_vault()
    return CredentialResolver(vault)


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_demo())
