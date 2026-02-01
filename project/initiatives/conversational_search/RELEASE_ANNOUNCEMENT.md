# Conversational Search Demo Suite - Release v0.1

**Release Date:** December 9, 2025
**Status:** Production Ready

---

## Overview

We're excited to announce the release of the **Conversational Search Demo Suite** - a comprehensive collection of five progressive demo workflows showcasing the full capabilities of Orcheo's conversational search node package. This release represents the completion of all four milestones outlined in our project plan and delivers production-ready examples for building sophisticated RAG and conversational search applications.

## What's Included

### Five Progressive Demo Workflows

1. **Demo 1: Hybrid Indexing**
   - Index corpus into Pinecone for downstream demos
   - Prerequisite for Demos 3, 4, and 6

2. **Demo 2: Basic RAG Pipeline**
   - Minimal ingestion and retrieval workflow
   - Works entirely locally with in-memory vector store
   - Perfect starting point for understanding core concepts
   - Quickstart time: ~2 minutes

3. **Demo 3: Hybrid Search**
   - Dense + sparse retrieval with fusion
   - Integration with Tavily for web search augmentation
   - Advanced reranking and result combination strategies

4. **Demo 4: Conversational Search**
   - Stateful multi-turn conversations
   - Query rewriting and context management
   - Memory management and history compression

5. **Demo 5: Production-Ready Pipeline**
   - Production guardrails and compliance checks
   - Answer caching and streaming support
   - Hallucination detection and citation verification

6. **Demo 6: Evaluation & Research**
   - Comprehensive evaluation metrics (retrieval, generation, end-to-end)
   - Golden datasets and feedback collection
   - A/B testing and failure analysis
   - Analytics export and reporting

### Shared Infrastructure

- **Sample Data**: Curated corpus, baseline queries, and golden labels
- **Utilities**: Reusable helpers for loading configs and datasets
- **Setup Checker**: Interactive prerequisite validation (`check_setup.py`)
- **Comprehensive Documentation**: Individual READMEs for each demo with setup instructions

## Quality Assurance

✅ **All 321 regression tests passing**
- Comprehensive test coverage across all conversational search nodes
- Tests cover ingestion, retrieval, conversation, generation, evaluation, and production features
- Edge cases and error handling fully validated

✅ **Documentation Complete**
- Main suite README with quickstart guide
- Individual demo READMEs with specific requirements
- Architecture diagrams and design documentation
- Troubleshooting guides and credential setup

✅ **Developer Experience**
- Quickstart under 5 minutes for Demo 1
- Interactive setup checker for prerequisites
- Clear credential management using Orcheo vault
- Consistent patterns across all demos

## Getting Started

### Prerequisites

```bash
# Install dependencies
uv sync --group examples

# Set up OpenAI credentials (required for all demos)
orcheo credential create openai_api_key --secret sk-your-key-here
```

### Run the Setup Checker

```bash
python examples/conversational_search/check_setup.py
```

This validates your Python version, dependencies, credentials, and sample data.

### Try Demo 2 (Recommended First Demo)

```bash
python examples/conversational_search/demo_2_basic_rag/demo_2.py
```

Demo 2 works entirely locally with no external vector database required, making it the perfect introduction to the suite.

## Architecture Highlights

- **Node-based Design**: Composable nodes for ingestion, retrieval, generation, and evaluation
- **State Management**: Clean state flow between nodes with variable interpolation
- **Multiple Backends**: Support for in-memory, Pinecone, and custom vector stores
- **Production Features**: Guardrails, caching, streaming, compliance checks
- **Evaluation Framework**: Built-in metrics, golden datasets, and feedback loops

## What's Next

This release provides a solid foundation for building conversational search applications. Each demo is designed to be:

- **Self-contained**: Run independently with clear setup instructions
- **Extensible**: Easy to adapt to your own domain and use cases
- **Educational**: Progressive complexity from basic to production-ready

We encourage you to:
1. Start with Demo 2 to understand core concepts
2. Explore Demos 3-4 for advanced retrieval and conversation patterns
3. Review Demo 5 for production deployment considerations
4. Use Demo 6 as a template for evaluation and continuous improvement

## Technical Details

- **Test Coverage**: 321 tests across all conversational search nodes
- **Python Version**: 3.12+
- **Key Dependencies**: LangGraph, LangChain, Pydantic, FastAPI
- **Supported Vector Stores**: In-memory, Pinecone
- **LLM Providers**: OpenAI (primary), extensible to other providers

## Documentation

- [Main README](../../examples/conversational_search/README.md)
- [Demo Design Document](demo_design.md)
- [Project Plan](demo_plan.md)
- [Requirements Document](requirements.md)

## Feedback and Support

We welcome feedback and contributions! For issues or questions:
- GitHub Issues: [github.com/ShaojieJiang/orcheo/issues](https://github.com/ShaojieJiang/orcheo/issues)
- Documentation: See individual demo READMEs

---

**Version**: 0.1
**Release Date**: December 9, 2025
**Milestone**: All 4 milestones complete (Foundations, Core Demos, Production & Evaluation, Documentation & UX)
