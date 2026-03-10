import type { Workflow } from "../workflow-types";
import type { WorkflowTemplateDefinition } from "./template-definition";
import { TEMPLATE_OWNER } from "./template-owner";
import mongodbQaAgentConfig from "./assets/mongodb-qa-agent/config.json";
import mongodbQaAgentScript from "./assets/mongodb-qa-agent/workflow.py?raw";

const MONGODB_QA_AGENT_MERMAID = `---
config:
  flowchart:
    curve: linear
---
graph TD;
	root__start(["START"]):::first
	root__node__agent["agent"]
	subgraph root__agent__tool__mongodb_hybrid_search__subgraph["mongodb_hybrid_search"]
		root__agent__tool__mongodb_hybrid_search__start(["START"]):::toolBoundary
		root__agent__tool__mongodb_hybrid_search__node__adapt_results["adapt_results"]:::tool
		root__agent__tool__mongodb_hybrid_search__node__format_results["format_results"]:::tool
		root__agent__tool__mongodb_hybrid_search__node__hybrid_search["hybrid_search"]:::tool
		root__agent__tool__mongodb_hybrid_search__node__query_embedding["query_embedding"]:::tool
		root__agent__tool__mongodb_hybrid_search__end(["END"]):::toolBoundary
		root__agent__tool__mongodb_hybrid_search__start --> root__agent__tool__mongodb_hybrid_search__node__query_embedding;
		root__agent__tool__mongodb_hybrid_search__node__adapt_results --> root__agent__tool__mongodb_hybrid_search__node__format_results;
		root__agent__tool__mongodb_hybrid_search__node__format_results --> root__agent__tool__mongodb_hybrid_search__end;
		root__agent__tool__mongodb_hybrid_search__node__hybrid_search --> root__agent__tool__mongodb_hybrid_search__node__adapt_results;
		root__agent__tool__mongodb_hybrid_search__node__query_embedding --> root__agent__tool__mongodb_hybrid_search__node__hybrid_search;
	end
	root__node__agent -.-> root__agent__tool__mongodb_hybrid_search__start;
	root__end(["END"]):::last
	root__start --> root__node__agent;
	root__node__agent --> root__end;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
	classDef tool fill:#e8f6ef,stroke:#4d8f6a,line-height:1.2
	classDef toolBoundary fill:#f6faf8,stroke:#8ab79c,stroke-dasharray: 4 4
`;

export const MONGODB_QA_AGENT_WORKFLOW: Workflow = {
  id: "template-mongodb-qa-agent",
  name: "MongoDB QA Agent",
  description:
    "An agent workflow that searches a MongoDB collection to answer user questions.",
  createdAt: "2026-03-10T09:00:00Z",
  updatedAt: "2026-03-10T09:00:00Z",
  sourceExample: "examples/mongodb_agent/03_qa_agent.py",
  owner: TEMPLATE_OWNER,
  tags: ["template", "python", "agent", "mongodb"],
  nodes: [
    {
      id: "start",
      type: "start",
      position: { x: 0, y: 0 },
      data: {
        label: "Start",
        type: "start",
        description: "Entry point for chat messages and workflow inputs.",
      },
    },
    {
      id: "agent",
      type: "agent",
      position: { x: 280, y: 0 },
      data: {
        label: "AgentNode",
        type: "agent",
        description:
          "Uses a MongoDB hybrid-search tool to retrieve context and draft replies.",
      },
    },
    {
      id: "end",
      type: "end",
      position: { x: 560, y: 0 },
      data: {
        label: "Finish",
        type: "end",
        description: "Workflow completes after the agent returns a response.",
      },
    },
  ],
  edges: [
    {
      id: "edge-start-agent",
      source: "start",
      target: "agent",
    },
    {
      id: "edge-agent-end",
      source: "agent",
      target: "end",
    },
  ],
  versions: [
    {
      id: "template-mongodb-qa-agent-v1",
      mermaid: MONGODB_QA_AGENT_MERMAID,
    },
  ],
};

export const MONGODB_QA_AGENT_TEMPLATE: WorkflowTemplateDefinition = {
  workflow: MONGODB_QA_AGENT_WORKFLOW,
  script: mongodbQaAgentScript,
  runnableConfig: mongodbQaAgentConfig,
  notes: "Seeded from MongoDB QA Agent template.",
};
