import React from "react";
import WorkflowNode from "@features/workflow/components/nodes/workflow-node";
import StartEndNode from "@features/workflow/components/nodes/start-end-node";
import GroupNode from "@features/workflow/components/nodes/group-node";
import { getNodeIcon } from "@features/workflow/lib/node-icons";

export const NODE_CATEGORIES = {
  all: "All Nodes",
  special: "Special Nodes",
  triggers: "Triggers",
  actions: "Actions",
  logic: "Logic & Flow",
  data: "Data Processing",
  ai: "AI & ML",
} as const;

export type NodeCategory = keyof typeof NODE_CATEGORIES;

export interface NodeGalleryItem {
  id: string;
  category: NodeCategory;
  component: React.ReactNode;
}

export const NODE_GALLERY_ITEMS: NodeGalleryItem[] = [
  {
    id: "start-node",
    category: "special",
    component: (
      <StartEndNode
        id="start-node"
        data={{
          label: "Workflow Start",
          type: "start",
          description: "Beginning of the workflow",
        }}
      />
    ),
  },
  {
    id: "end-node",
    category: "special",
    component: (
      <StartEndNode
        id="end-node"
        data={{
          label: "Workflow End",
          type: "end",
          description: "End of the workflow",
        }}
      />
    ),
  },
  {
    id: "group-node",
    category: "special",
    component: (
      <GroupNode
        id="group-node"
        data={{
          label: "Node Group",
          description: "Group related nodes together",
          nodeCount: 3,
          color: "blue",
        }}
      />
    ),
  },
  {
    id: "webhook-trigger",
    category: "triggers",
    component: (
      <WorkflowNode
        id="webhook-trigger"
        data={{
          label: "Webhook",
          description: "Trigger on HTTP webhook",
          iconKey: "webhook",
          icon: getNodeIcon("webhook"),
          type: "trigger",
        }}
      />
    ),
  },
  {
    id: "manual-trigger",
    category: "triggers",
    component: (
      <WorkflowNode
        id="manual-trigger"
        data={{
          label: "Manual",
          description: "Trigger on-demand from the dashboard",
          iconKey: "manualTrigger",
          icon: getNodeIcon("manualTrigger"),
          type: "trigger",
        }}
      />
    ),
  },
  {
    id: "http-polling-trigger",
    category: "triggers",
    component: (
      <WorkflowNode
        id="http-polling-trigger"
        data={{
          label: "HTTP Polling",
          description: "Poll an API on a schedule",
          iconKey: "httpPolling",
          icon: getNodeIcon("httpPolling"),
          type: "trigger",
        }}
      />
    ),
  },
  {
    id: "schedule-trigger",
    category: "triggers",
    component: (
      <WorkflowNode
        id="schedule-trigger"
        data={{
          label: "Schedule",
          description: "Trigger on schedule",
          iconKey: "schedule",
          icon: getNodeIcon("schedule"),
          type: "trigger",
        }}
      />
    ),
  },
  {
    id: "http-request",
    category: "actions",
    component: (
      <WorkflowNode
        id="http-request"
        data={{
          label: "HTTP Request",
          description: "Make HTTP requests",
          iconKey: "http",
          icon: getNodeIcon("http"),
          type: "api",
        }}
      />
    ),
  },
  {
    id: "email-send",
    category: "actions",
    component: (
      <WorkflowNode
        id="email-send"
        data={{
          label: "Send Email",
          description: "Send an email",
          iconKey: "email",
          icon: getNodeIcon("email"),
          type: "api",
        }}
      />
    ),
  },
  {
    id: "condition",
    category: "logic",
    component: (
      <WorkflowNode
        id="condition"
        data={{
          label: "If / Else",
          description: "Branch based on a comparison",
          iconKey: "condition",
          icon: getNodeIcon("condition"),
          type: "function",
        }}
      />
    ),
  },
  {
    id: "loop",
    category: "logic",
    component: (
      <WorkflowNode
        id="loop"
        data={{
          label: "While Loop",
          description: "Iterate while a condition is true",
          iconKey: "loop",
          icon: getNodeIcon("loop"),
          type: "function",
        }}
      />
    ),
  },
  {
    id: "transform",
    category: "data",
    component: (
      <WorkflowNode
        id="transform"
        data={{
          label: "Transform",
          description: "Transform data",
          iconKey: "transform",
          icon: getNodeIcon("transform"),
          type: "data",
        }}
      />
    ),
  },
  {
    id: "python-code",
    category: "data",
    component: (
      <WorkflowNode
        id="python-code"
        data={{
          label: "Python Code",
          description: "Execute custom Python scripts",
          iconKey: "python",
          icon: getNodeIcon("python"),
          type: "python",
        }}
      />
    ),
  },
  {
    id: "database",
    category: "data",
    component: (
      <WorkflowNode
        id="database"
        data={{
          label: "Database",
          description: "Query database",
          iconKey: "database",
          icon: getNodeIcon("database"),
          type: "data",
        }}
      />
    ),
  },
  {
    id: "text-generation",
    category: "ai",
    component: (
      <WorkflowNode
        id="text-generation"
        data={{
          label: "Text Generation",
          description: "Generate text with AI",
          iconKey: "textGeneration",
          icon: getNodeIcon("textGeneration"),
          type: "ai",
        }}
      />
    ),
  },
  {
    id: "chat-completion",
    category: "ai",
    component: (
      <WorkflowNode
        id="chat-completion"
        data={{
          label: "Chat Completion",
          description: "Generate chat responses",
          iconKey: "chatCompletion",
          icon: getNodeIcon("chatCompletion"),
          type: "ai",
        }}
      />
    ),
  },
];
