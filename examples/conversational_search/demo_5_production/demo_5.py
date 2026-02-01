"""Production-ready conversational search demo highlighting guardrails and caching."""

from collections import OrderedDict
from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from pydantic import Field
from orcheo.edges import Switch, SwitchCase
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.conversation import (
    AnswerCachingNode,
    ConversationStateNode,
    InMemoryMemoryStore,
    SessionManagementNode,
)
from orcheo.nodes.conversational_search.embedding_registry import (
    OPENAI_TEXT_EMBEDDING_3_SMALL,
)
from orcheo.nodes.conversational_search.evaluation import (
    MemoryPrivacyNode,
    PolicyComplianceNode,
)
from orcheo.nodes.conversational_search.generation import (
    GroundedGeneratorNode,
    HallucinationGuardNode,
    StreamingGeneratorNode,
)
from orcheo.nodes.conversational_search.query_processing import (
    MultiHopPlannerNode,
    QueryRewriteNode,
)
from orcheo.nodes.conversational_search.retrieval import (
    DenseSearchNode,
    SourceRouterNode,
)
from orcheo.nodes.conversational_search.vector_store import (
    BaseVectorStore,
    InMemoryVectorStore,
    PineconeVectorStore,
)
from orcheo.runtime.credentials import CredentialResolver, credential_resolution


SESSION_ID = "demo-4-session"
CONVERSATION_TURNS = [
    "What authentication options does Orcheo Cloud expose?",
    "How do I rotate API keys and monitor retrieval latency?",
    "What guardrails keep streaming responses grounded in production?",
]

DEFAULT_CONFIG: dict[str, Any] = {
    "retrieval": {
        "vector_store": {
            "type": "pinecone",
            "index_name": "orcheo-demo-dense",
            "namespace": "hybrid_search",
            "client_kwargs": {
                "api_key": "[[pinecone_api_key]]",
            },
        },
        "top_k": 4,
        "score_threshold": 0.0,
        "embedding_method": OPENAI_TEXT_EMBEDDING_3_SMALL,
    },
    "session": {
        "max_sessions": 8,
        "max_turns": 20,
        "max_total_turns": 200,
    },
    "caching": {
        "ttl_seconds": 3600,
        "max_entries": 128,
    },
    "multi_hop": {"max_hops": 3},
    "memory_privacy": {"retention_count": 32},
    "guardrails": {
        "blocked_terms": ["password", "ssn"],
    },
    "streaming": {"chunk_size": 8, "buffer_limit": 64},
}


class ResultToInputsNode(TaskNode):
    """Copy values out of a result entry into the running input payload."""

    source_result_key: str = Field(
        default="grounded_generator", description="Result entry to read from."
    )
    mappings: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of target input key -> source field path",
    )
    allow_missing: bool = Field(
        default=True,
        description="If true, missing source fields are ignored.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Populate inputs using the configured result mappings."""
        results = state.get("results", {})
        payload = results.get(self.source_result_key, {})
        if not isinstance(payload, dict):
            return {"mapped_keys": []}

        inputs = state.get("inputs") or {}
        state["inputs"] = inputs

        mapped: list[str] = []
        for target_key, source_path in self.mappings.items():
            value = payload
            for segment in source_path.split("."):
                if not isinstance(value, dict) or segment not in value:
                    value = None
                    break
                value = value.get(segment)
            if value is None:
                if not self.allow_missing:
                    raise ValueError(
                        f"Field '{source_path}' missing from {self.source_result_key}"
                    )
                continue
            inputs[target_key] = value
            mapped.append(target_key)
        return {"mapped_keys": mapped}


class PlanToSearchQueryNode(TaskNode):
    """Use the multi-hop plan to pick the next search query."""

    plan_source: str = Field(default="multi_hop", description="Plan entry key.")
    plan_key: str = Field(default="plan", description="Plan payload field.")
    query_key: str = Field(default="search_query", description="Target query key.")
    plan_target_key: str = Field(
        default="multi_hop_plan", description="Where to stash the plan."
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Select the next search query from the multi-hop plan."""
        results = state.get("results", {})
        plan_payload = results.get(self.plan_source, {})
        plan_entries = plan_payload.get(self.plan_key) or []
        normalized = [
            entry
            for entry in plan_entries
            if isinstance(entry, dict) and isinstance(entry.get("query"), str)
        ]

        inputs = state.get("inputs") or {}
        state["inputs"] = inputs
        inputs[self.plan_target_key] = normalized

        selected_query = (
            normalized[0]["query"] if normalized else inputs.get(self.query_key)
        )
        if selected_query:
            inputs[self.query_key] = selected_query

        return {"selected_query": selected_query, "hop_count": len(normalized)}


def merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Return a deep merge of ``override`` into ``base`` without mutating."""
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def build_vector_store_from_config(cfg: dict[str, Any] | None) -> BaseVectorStore:
    """Instantiate the requested vector store implementation."""
    cfg = cfg or {}
    store_type = str(cfg.get("type", "pinecone")).lower()
    if store_type == "pinecone":
        pinecone_cfg = dict(cfg.get("pinecone") or cfg)
        index_name = pinecone_cfg.get("index_name")
        if not index_name:
            raise ValueError("Pinecone vector store config requires 'index_name'")
        client_kwargs = dict(pinecone_cfg.get("client_kwargs") or {})
        return PineconeVectorStore(
            index_name=index_name,
            namespace=pinecone_cfg.get("namespace"),
            client_kwargs=client_kwargs,
        )
    return InMemoryVectorStore()


def build_demo_nodes(
    *,
    vector_store: BaseVectorStore,
    memory_store: InMemoryMemoryStore,
    retrieval_cfg: dict[str, Any],
    session_cfg: dict[str, Any],
    caching_cfg: dict[str, Any],
    multi_hop_cfg: dict[str, Any],
    privacy_cfg: dict[str, Any],
    streaming_cfg: dict[str, Any],
    shared_cache: OrderedDict[str, tuple[str, float | None]],
    guardrails: list[str],
) -> dict[str, TaskNode]:
    """Create the nodes that drive the production conversational graph."""
    nodes: dict[str, TaskNode] = {}

    nodes["session_manager"] = SessionManagementNode(
        name="session_manager",
        memory_store=memory_store,
        max_turns=session_cfg.get("max_turns"),
    )

    nodes["conversation_state"] = ConversationStateNode(
        name="conversation_state",
        memory_store=memory_store,
        max_turns=session_cfg.get("max_turns"),
    )

    nodes["conversation_history_sync"] = ResultToInputsNode(
        name="conversation_history_sync",
        source_result_key=nodes["conversation_state"].name,
        mappings={
            "history": "conversation_history",
            "conversation_history": "conversation_history",
        },
    )

    nodes["answer_cache_check"] = AnswerCachingNode(
        name="answer_cache_check",
        cache=shared_cache,
        ttl_seconds=caching_cfg.get("ttl_seconds"),
        max_entries=caching_cfg.get("max_entries", 128),
        source_result_key="policy_compliance",
        response_field="sanitized",
    )

    nodes["query_rewrite"] = QueryRewriteNode(name="query_rewrite")
    nodes["rewrite_to_search"] = ResultToInputsNode(
        name="rewrite_to_search",
        source_result_key=nodes["query_rewrite"].name,
        mappings={"search_query": "query"},
    )

    nodes["multi_hop_planner"] = MultiHopPlannerNode(
        name="multi_hop_planner",
        query_key="search_query",
        max_hops=multi_hop_cfg.get("max_hops", 3),
    )
    nodes["plan_to_search_query"] = PlanToSearchQueryNode(name="plan_to_search_query")

    nodes["dense_search"] = DenseSearchNode(
        name="dense_search",
        vector_store=vector_store,
        embedding_method=retrieval_cfg.get(
            "embedding_method", OPENAI_TEXT_EMBEDDING_3_SMALL
        ),
        top_k=retrieval_cfg.get("top_k", 4),
        score_threshold=retrieval_cfg.get("score_threshold", 0.0),
        query_key="search_query",
    )
    nodes["source_router"] = SourceRouterNode(
        name="source_router",
        source_result_key=nodes["dense_search"].name,
        min_score=retrieval_cfg.get("score_threshold", 0.0),
    )

    nodes["grounded_generator"] = GroundedGeneratorNode(
        name="grounded_generator",
        context_result_key=nodes["dense_search"].name,
        ai_model="openai:gpt-4o-mini",
        citation_style="inline",
    )

    nodes["hallucination_guard"] = HallucinationGuardNode(
        name="hallucination_guard",
        generator_result_key=nodes["grounded_generator"].name,
    )

    nodes["guard_to_policy"] = ResultToInputsNode(
        name="guard_to_policy",
        source_result_key=nodes["hallucination_guard"].name,
        mappings={"content": "reply"},
    )

    nodes["policy_compliance"] = PolicyComplianceNode(
        name="policy_compliance",
        blocked_terms=guardrails,
    )

    nodes["memory_privacy"] = MemoryPrivacyNode(
        name="memory_privacy",
        retention_count=privacy_cfg.get("retention_count"),
    )

    nodes["answer_cache_store"] = AnswerCachingNode(
        name="answer_cache_store",
        cache=shared_cache,
        ttl_seconds=caching_cfg.get("ttl_seconds"),
        max_entries=caching_cfg.get("max_entries", 128),
        source_result_key=nodes["policy_compliance"].name,
        response_field="sanitized",
    )

    nodes["policy_to_stream_inputs"] = ResultToInputsNode(
        name="policy_to_stream_inputs",
        source_result_key=nodes["policy_compliance"].name,
        mappings={
            "stream_prompt": "sanitized",
            "assistant_message": "sanitized",
        },
    )

    streaming = StreamingGeneratorNode(
        name="streaming_generator",
        prompt_key="stream_prompt",
        chunk_size=streaming_cfg.get("chunk_size", 8),
        buffer_limit=streaming_cfg.get("buffer_limit", 64),
        ai_model="openai:gpt-4o-mini",
    )
    nodes["streaming_generator"] = streaming

    nodes["conversation_state_update"] = ConversationStateNode(
        name="conversation_state_update",
        memory_store=memory_store,
        user_message_key="__unused__",
        assistant_message_key="assistant_message",
        max_turns=session_cfg.get("max_turns"),
    )

    nodes["cache_hit_to_inputs"] = ResultToInputsNode(
        name="cache_hit_to_inputs",
        source_result_key=nodes["answer_cache_check"].name,
        mappings={
            "content": "reply",
            "stream_prompt": "reply",
            "assistant_message": "reply",
        },
    )

    return nodes


def assemble_demo_workflow(nodes: dict[str, TaskNode]) -> StateGraph:
    """Wire the provided nodes together into the demo StateGraph."""
    workflow = StateGraph(State)
    for node in nodes.values():
        workflow.add_node(node.name, node)

    workflow.set_entry_point(nodes["session_manager"].name)

    initial_edges = [
        ("session_manager", "conversation_state"),
        ("conversation_state", "conversation_history_sync"),
        ("conversation_history_sync", "answer_cache_check"),
    ]

    for src, dst in initial_edges:
        workflow.add_edge(nodes[src].name, nodes[dst].name)

    cache_switch = Switch(
        name="cache_routing",
        value=f"{{{{{nodes['answer_cache_check'].name}.cached}}}}",
        case_sensitive=False,
        default_branch_key="miss",
        cases=[SwitchCase(match=True, branch_key="hit")],
    )

    workflow.add_conditional_edges(
        nodes["answer_cache_check"].name,
        cache_switch,
        {
            "hit": nodes["cache_hit_to_inputs"].name,
            "miss": nodes["query_rewrite"].name,
        },
    )

    routing_edges = [
        ("cache_hit_to_inputs", "conversation_state_update"),
        ("query_rewrite", "rewrite_to_search"),
        ("rewrite_to_search", "multi_hop_planner"),
        ("multi_hop_planner", "plan_to_search_query"),
        ("plan_to_search_query", "dense_search"),
        ("dense_search", "source_router"),
        ("source_router", "grounded_generator"),
        ("grounded_generator", "hallucination_guard"),
        ("hallucination_guard", "guard_to_policy"),
        ("guard_to_policy", "policy_compliance"),
        ("policy_compliance", "memory_privacy"),
        ("memory_privacy", "answer_cache_store"),
        ("answer_cache_store", "policy_to_stream_inputs"),
        ("policy_to_stream_inputs", "streaming_generator"),
        ("streaming_generator", "conversation_state_update"),
    ]

    for src, dst in routing_edges:
        workflow.add_edge(nodes[src].name, nodes[dst].name)

    workflow.add_edge(nodes["conversation_state_update"].name, END)

    return workflow


async def build_graph(
    *,
    config: dict[str, Any] | None = None,
    vector_store: BaseVectorStore | None = None,
    memory_store: InMemoryMemoryStore | None = None,
) -> StateGraph:
    """Assemble the production workflow graph described in the design doc."""
    merged_config = merge_dicts(DEFAULT_CONFIG, config or {})
    retrieval_cfg = merged_config["retrieval"]
    vector_cfg = retrieval_cfg["vector_store"]
    session_cfg = merged_config["session"]
    caching_cfg = merged_config["caching"]
    multi_hop_cfg = merged_config["multi_hop"]
    privacy_cfg = merged_config["memory_privacy"]
    streaming_cfg = merged_config["streaming"]

    vector_store = vector_store or build_vector_store_from_config(vector_cfg)
    memory_store = memory_store or InMemoryMemoryStore(
        max_sessions=session_cfg.get("max_sessions"),
        max_total_turns=session_cfg.get("max_total_turns"),
    )

    shared_cache: OrderedDict[str, tuple[str, float | None]] = OrderedDict()

    nodes = build_demo_nodes(
        vector_store=vector_store,
        memory_store=memory_store,
        retrieval_cfg=retrieval_cfg,
        session_cfg=session_cfg,
        caching_cfg=caching_cfg,
        multi_hop_cfg=multi_hop_cfg,
        privacy_cfg=privacy_cfg,
        streaming_cfg=streaming_cfg,
        shared_cache=shared_cache,
        guardrails=merged_config["guardrails"].get("blocked_terms", []),
    )

    return assemble_demo_workflow(nodes)


def print_demo_introduction(retrieval_cfg: dict[str, Any]) -> None:
    """Emit configuration cues for the demo run."""
    vector_cfg = retrieval_cfg["vector_store"]
    print("Production pipeline config:", DEFAULT_CONFIG["session"])
    print(
        "This demo assumes the vector store",
        f"{vector_cfg.get('index_name')} (namespace={vector_cfg.get('namespace')})",
        "already stores embeddings (run Demo 0 first).",
    )


def print_plan_details(plan: list[dict[str, Any]]) -> None:
    """Pretty-print multi-hop details."""
    if not plan:
        return
    print(" Multi-hop plan:")
    for hop in plan:
        identifier = hop.get("id", "<unnamed>")
        query = hop.get("query")
        depends = hop.get("depends_on")
        print(f"  - {identifier}: {query} (depends on {depends})")


def print_cached_response(cached_reply: str | None) -> None:
    """Show cached answer metadata before returning (guardrails already satisfied)."""
    print(" Cache hit: serving cached answer.")
    if cached_reply:
        print(" Cached reply:", cached_reply)


def print_cached_final_reply(cached_reply: str | None) -> None:
    """Emit cached policy/memory/response summaries."""
    print(" Policy compliance: cached answer (pre-sanitized)")
    if cached_reply:
        print(" Sanitized reply:", cached_reply)
    print(" Memory privacy: cached answer (no new evaluation)")
    print(" Final reply:", cached_reply)


def print_uncached_retrieval_details(results: dict[str, Any]) -> None:
    """Log plan, retrieval hits, routing decisions, and guardrail status."""
    plan = results.get("multi_hop_planner", {}).get("plan", [])
    if plan:
        print_plan_details(plan)

    hits = results.get("dense_search", {}).get("results", [])
    if hits:
        print(" Retrieval hits:")
        for rank, hit in enumerate(hits[:3], start=1):
            score = hit.get("score", 0.0)
            title = hit.get("metadata", {}).get("source") or hit.get("id")
            print(f"  {rank}. {title} (score={score:.2f})")

    router = results.get("source_router", {}).get("routed", {})
    if router:
        print(" Sources routed:")
        for source, entries in router.items():
            print(f"  - {source}: {len(entries)} hits")

    guard = results.get("hallucination_guard", {})
    allowed = guard.get("allowed")
    print(" Hallucination guard:", "allowed" if allowed else "blocked")


def print_uncached_final_reply(results: dict[str, Any]) -> None:
    """Emit policy evaluation, streaming output, and privacy state for new answers."""
    policy = results.get("policy_compliance", {})
    print(" Policy compliance:", policy.get("compliant"))
    print(" Sanitized reply:", policy.get("sanitized"))

    streaming = results.get("streaming_generator", {})
    frames = streaming.get("frames", [])
    if frames:
        print(" Streaming frames (chunk text):")
        for frame in frames[:3]:
            print(f"  - {frame.get('chunk')}")

    privacy = results.get("memory_privacy", {})
    sanitized_history = privacy.get("sanitized_history", [])
    print(" Memory privacy: stored", len(sanitized_history), "turns")

    print(" Final streaming reply:", streaming.get("reply"))


async def process_demo_turn(app: Any, turn_index: int, message: str) -> None:
    """Drive the graph for a user turn and surface guardrail outputs."""
    print(f"\n--- Turn {turn_index}: {message}")
    payload = {
        "inputs": {
            "session_id": SESSION_ID,
            "message": message,
            "user_message": message,
            "search_query": message,
        }
    }
    result = await app.ainvoke(payload)  # type: ignore[arg-type]
    results = result.get("results", {})

    cache_status = results.get("answer_cache_check", {})
    cached = cache_status.get("cached", False)
    cached_reply = cache_status.get("reply")
    if cached:
        print_cached_response(cached_reply)
        print_cached_final_reply(cached_reply)
        return

    print_uncached_retrieval_details(results)
    print_uncached_final_reply(results)


async def run_demo() -> None:
    """Run production demo with sample turns against a prepopulated index."""
    retrieval_cfg = DEFAULT_CONFIG["retrieval"]
    vector_store = build_vector_store_from_config(retrieval_cfg["vector_store"])
    print_demo_introduction(retrieval_cfg)

    workflow = await build_graph(vector_store=vector_store)
    app = workflow.compile()
    resolver = setup_credentials()

    with credential_resolution(resolver):
        for turn_index, message in enumerate(CONVERSATION_TURNS, start=1):
            await process_demo_turn(app, turn_index, message)

    print("\nDemo run complete.")


def setup_credentials() -> CredentialResolver:
    """Return the resolver that exposes the Pinecone credential."""
    from orcheo_backend.app.dependencies import get_vault

    vault = get_vault()
    return CredentialResolver(vault)


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_demo())
