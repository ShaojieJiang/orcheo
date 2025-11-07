import React from "react";
import { GitBranch } from "lucide-react";

import { buildSidebarNode, type NodeCategory } from "../sidebar-panel.types";

export const logicCategory: NodeCategory = {
  id: "logic",
  name: "Logic & Flow",
  icon: <GitBranch className="h-4 w-4 text-purple-500" />,
  nodes: [
    buildSidebarNode({
      id: "condition",
      name: "If / Else",
      description: "Branch based on a comparison",
      iconKey: "condition",
      type: "function",
      backendType: "IfElseNode",
      data: {
        conditionLogic: "and",
        conditions: [
          {
            id: "condition-1",
            left: "{{previous.result}}",
            operator: "equals",
            right: "expected",
            caseSensitive: false,
          },
        ],
        outputs: [
          { id: "true", label: "True" },
          { id: "false", label: "False" },
        ],
      },
    }),
    buildSidebarNode({
      id: "loop",
      name: "While Loop",
      description: "Iterate while a condition remains true",
      iconKey: "loop",
      type: "function",
      backendType: "WhileNode",
      data: {
        conditionLogic: "and",
        conditions: [
          {
            id: "condition-1",
            operator: "less_than",
            right: 3,
          },
        ],
        maxIterations: 10,
        outputs: [
          { id: "continue", label: "Continue" },
          { id: "exit", label: "Exit" },
        ],
      },
    }),
    buildSidebarNode({
      id: "switch",
      name: "Switch",
      description: "Multiple conditional branches",
      iconKey: "switch",
      type: "function",
      backendType: "SwitchNode",
      data: {
        value: "{{previous.status}}",
        caseSensitive: false,
        defaultBranchKey: "default",
        cases: [
          {
            id: "case-1",
            match: "approved",
            label: "Approved",
            branchKey: "approved",
          },
          {
            id: "case-2",
            match: "rejected",
            label: "Rejected",
            branchKey: "rejected",
          },
        ],
        outputs: [
          { id: "approved", label: "Approved" },
          { id: "rejected", label: "Rejected" },
          { id: "default", label: "Default" },
        ],
      },
    }),
    buildSidebarNode({
      id: "delay",
      name: "Delay",
      description: "Pause workflow execution",
      iconKey: "delay",
      type: "function",
      backendType: "DelayNode",
      data: {
        durationSeconds: 5,
      },
    }),
    buildSidebarNode({
      id: "error-handler",
      name: "Error Handler",
      description: "Handle errors in workflow",
      iconKey: "errorHandler",
      type: "function",
    }),
    buildSidebarNode({
      id: "set-variable",
      name: "Set Variable",
      description: "Store a value for downstream steps",
      iconKey: "setVariable",
      type: "function",
      backendType: "SetVariableNode",
      data: {
        variables: [
          {
            name: "my_variable",
            valueType: "string",
            value: "sample",
          },
        ],
        outputs: [{ id: "default" }],
      },
    }),
  ],
};
