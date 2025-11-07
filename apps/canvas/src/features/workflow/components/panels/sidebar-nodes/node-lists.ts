import { DEFAULT_PYTHON_CODE } from "@features/workflow/lib/python-node";

import { buildSidebarNode, type SidebarNode } from "../sidebar-panel.types";

export const recentNodes: SidebarNode[] = [
  buildSidebarNode({
    id: "http-recent",
    name: "HTTP Request",
    description: "Make HTTP requests to external APIs",
    iconKey: "http",
    type: "api",
  }),
  buildSidebarNode({
    id: "python-recent",
    name: "Python Code",
    description: "Execute custom Python scripts",
    iconKey: "python",
    type: "python",
    data: {
      code: DEFAULT_PYTHON_CODE,
    },
  }),
  buildSidebarNode({
    id: "text-generation-recent",
    name: "Text Generation",
    description: "Generate text with AI models",
    iconKey: "textGeneration",
    type: "ai",
  }),
  buildSidebarNode({
    id: "start-node-recent",
    name: "Workflow Start",
    description: "Beginning of the workflow",
    iconKey: "start",
    type: "start",
  }),
  buildSidebarNode({
    id: "end-node-recent",
    name: "Workflow End",
    description: "End of the workflow",
    iconKey: "end",
    type: "end",
  }),
];

export const favoriteNodes: SidebarNode[] = [
  buildSidebarNode({
    id: "http-favorite",
    name: "HTTP Request",
    description: "Make HTTP requests to external APIs",
    iconKey: "http",
    type: "api",
  }),
  buildSidebarNode({
    id: "transform-favorite",
    name: "Transform",
    description: "Transform data between steps",
    iconKey: "transform",
    type: "data",
  }),
  buildSidebarNode({
    id: "python-favorite",
    name: "Python Code",
    description: "Execute custom Python scripts",
    iconKey: "python",
    type: "python",
    data: {
      code: DEFAULT_PYTHON_CODE,
    },
  }),
];
