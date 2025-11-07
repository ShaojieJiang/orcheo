import { DEFAULT_PYTHON_CODE } from "@features/workflow/lib/python-node";
import { Workflow } from "../workflow-types";
import { TEMPLATE_OWNER } from "./template-owner";

export const SIMPLE_PYTHON_WORKFLOW: Workflow = {
  id: "workflow-python-hello",
  name: "Simple Python Task",
  description: "Runs a standalone PythonCode node and returns a greeting.",
  createdAt: "2024-01-18T12:00:00Z",
  updatedAt: "2024-03-10T09:15:00Z",
  owner: TEMPLATE_OWNER,
  tags: ["template", "python", "utility"],
  nodes: [
    {
      id: "python-start",
      type: "start",
      position: { x: 0, y: 0 },
      data: {
        label: "Start",
        type: "start",
        description: "Kick off the simple Python workflow.",
      },
    },
    {
      id: "python-greet",
      type: "python",
      position: { x: 260, y: 0 },
      data: {
        label: "Run Python code",
        type: "python",
        description: "PythonCode node that returns a hello message.",
        code: DEFAULT_PYTHON_CODE,
        codeExample: "return {'message': 'Hello from Python!'}",
      },
    },
    {
      id: "python-end",
      type: "end",
      position: { x: 520, y: 0 },
      data: {
        label: "Finish",
        type: "end",
        description: "Ends after the Python node executes.",
      },
    },
  ],
  edges: [
    {
      id: "edge-python-start-greet",
      source: "python-start",
      target: "python-greet",
    },
    {
      id: "edge-python-greet-end",
      source: "python-greet",
      target: "python-end",
    },
  ],
};
