# Project Plan

## For Conversational Search Demo Suite

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2025-11-25
- **Status:** Draft

---

## Overview

Execution plan to ship the five conversational search demo workflows that showcase the node package across ingestion, retrieval, conversation, production guardrails, and evaluation. Each milestone aligns with the demo design to ensure runnable artifacts, sample data, and documentation are delivered together.

**Related Documents:**
- Requirements: [PRD: Conversational Search Node Package](requirements.md)
- Design: [Demo Workflow Design](demo_design.md)

---

## Milestones

### Milestone 1: Demo Foundations & Data

**Description:** Establish demo skeletons, shared utilities, and sample datasets so every workflow can run locally with minimal setup.

#### Task Checklist

- [x] Task 1.1: Create demo directory structure and README scaffolds for demos 1-5.
  - Dependencies: Demo design file structure.
- [x] Task 1.2: Prepare sample corpora and golden datasets (docs, queries, labels) with environment templates.
  - Dependencies: Access to example content and eval labels.
- [x] Task 1.3: Add shared utilities (loaders, runners, config helpers) reused across demos.
  - Dependencies: Node package APIs for loaders/indexers.

---

### Milestone 2: Core & Conversational Demos (1-3)

**Description:** Implement runnable workflows for Basic RAG, Hybrid Search, and Conversational Search with configs, scripts, and smoke tests.

#### Task Checklist

- [x] Task 2.1: Ship Demo 1 (Basic RAG) with config, runner, sample data, and README.
  - Dependencies: Milestone 1 scaffolds and datasets.
- [x] Task 2.2: Ship Demo 2 (Hybrid Search) including fusion/rerank config, runner, and comparison notes.
  - Dependencies: Task 2.1 ingestion assets; Tavily/WebSearch access.
- [x] Task 2.3: Ship Demo 3 (Conversational) with stateful chat runner and multi-turn samples.
  - Dependencies: Task 2.1 conversation schema; memory store setup.
- [x] Task 2.4: Add smoke tests for demos 1-3 ensuring graph wiring and deterministic sample outputs.
  - Dependencies: Tasks 2.1-2.3 runnable workflows.

---

### Milestone 3: Production & Evaluation Demos (4-5)

**Description:** Deliver production-hardened and evaluation-focused workflows with guardrails, caching, streaming, and analytics.

#### Task Checklist

- [x] Task 3.1: Ship Demo 4 (Production-Ready) with guardrails, caching, streaming configs, and operational README.
  - Dependencies: Milestone 2 retrieval/generation components; policy definitions.
- [x] Task 3.2: Ship Demo 5 (Evaluation & Research) with metrics runners, feedback ingestion, and dashboards/exports.
  - Dependencies: Evaluation datasets; analytics sink or mock.
- [x] Task 3.3: Extend smoke and integration tests covering guardrail paths and evaluation metrics reporting.
  - Dependencies: Tasks 3.1-3.2 implementations.

---

### Milestone 4: Documentation, UX, and Release

**Description:** Finalize demo documentation, polish UX (CLI/notebooks), and validate end-to-end before publishing.

#### Task Checklist

- [x] Task 4.1: Complete README updates with setup, expected outputs, troubleshooting for all demos.
  - Dependencies: Milestones 2-3 content finalized.
- [x] Task 4.2: Add CLI prompts for guided runs; ensure quickstart under 5 minutes.
  - Dependencies: Demo runners stabilized.
- [ ] Task 4.3: Run full regression suite and update revision notes; prepare release announcement.
  - Dependencies: All demo tests passing; documentation complete.

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-11-26 | Codex | Initial draft |
