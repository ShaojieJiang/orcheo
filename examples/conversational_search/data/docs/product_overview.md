# Orcheo Cloud Overview

Orcheo Cloud is a managed platform for building stateful AI workflows. Teams use it to connect document ingestion, retrieval, and generation nodes into auditable graphs that can run on the edge or in the cloud.

## Core Capabilities
- **Graph Engine:** Build directed graphs with typed inputs and outputs for deterministic orchestration.
- **Node Library:** Reusable nodes for document loading, chunking, retrieval, generation, and evaluation.
- **Observability:** Structured traces for every node execution with metrics export.
- **Security:** Secrets stay in vault-backed connectors and workloads run in isolated sandboxes.

## Getting Started
1. Install the Orcheo CLI and authenticate with your workspace.
2. Define a graph in YAML or with the Python builder.
3. Run `orcheo dev` to iterate locally, then promote to staging and production.

## Documentation Map
- Architecture: `docs/architecture.md`
- Node Reference: `docs/nodes.md`
- Deployment Guide: `docs/deployments.md`

## Example Questions
- How do I add a custom node to my graph?
- What logging format does the graph engine emit?
- Which secrets providers are supported by default?
