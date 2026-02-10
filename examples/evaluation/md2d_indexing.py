r"""MultiDoc2Dial corpus indexing workflow.

Indexes the ~488-document MultiDoc2Dial corpus into a configured
vector store for use by the evaluation workflow.

Usage:
    orcheo workflow upload examples/evaluation/md2d_indexing.py \\
        --config-file examples/evaluation/config_md2d_indexing.json
    orcheo workflow run <workflow-id>
"""

from typing import Any
from langgraph.graph import END, StateGraph
from orcheo.graph.state import State
from orcheo.nodes.conversational_search.ingestion import (
    ChunkEmbeddingNode,
    ChunkingStrategyNode,
    VectorStoreUpsertNode,
)
from orcheo.nodes.conversational_search.vector_store import PineconeVectorStore
from orcheo.nodes.evaluation.datasets import MultiDoc2DialCorpusLoaderNode


def build_nodes() -> dict[str, Any]:
    """Create all nodes for the corpus indexing pipeline."""
    nodes: dict[str, Any] = {}

    nodes["loader"] = MultiDoc2DialCorpusLoaderNode(
        name="loader",
        corpus_path="{{config.configurable.corpus.docs_path}}",
        max_documents="{{config.configurable.corpus.max_documents}}",
    )

    nodes["chunker"] = ChunkingStrategyNode(
        name="chunker",
        source_result_key="loader",
        chunk_size="{{config.configurable.corpus.chunk_size}}",
        chunk_overlap="{{config.configurable.corpus.chunk_overlap}}",
    )

    nodes["embedder"] = ChunkEmbeddingNode(
        name="embedder",
        source_result_key="chunker",
        dense_embedding_specs={
            "default": {
                "embed_model": "{{config.configurable.retrieval.embed_model}}",
                "model_kwargs": {
                    "api_key": "[[openai_api_key]]",
                    "dimensions": "{{config.configurable.retrieval.dimensions}}",
                },
            }
        },
    )

    nodes["upsert"] = VectorStoreUpsertNode(
        name="upsert",
        source_result_key="embedder",
        vector_store=PineconeVectorStore(
            index_name="{{config.configurable.vector_store.pinecone.index_name}}",
            namespace="{{config.configurable.vector_store.pinecone.namespace}}",
            client_kwargs={"api_key": "[[pinecone_api_key]]"},
        ),
    )

    return nodes


async def orcheo_workflow() -> StateGraph:
    """Build the MultiDoc2Dial corpus indexing workflow graph."""
    nodes = build_nodes()

    workflow = StateGraph(State)
    for node in nodes.values():
        workflow.add_node(node.name, node)

    workflow.set_entry_point("loader")

    chain = [
        nodes["loader"],
        nodes["chunker"],
        nodes["embedder"],
        nodes["upsert"],
    ]

    for current, nxt in zip(chain, chain[1:], strict=False):
        workflow.add_edge(current.name, nxt.name)
    workflow.add_edge(chain[-1].name, END)

    return workflow
