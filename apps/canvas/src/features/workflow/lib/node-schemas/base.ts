import { RJSFSchema } from "@rjsf/utils";

import { comparisonOperatorEnum } from "@features/workflow/lib/node-schemas/condition-operators";

/**
 * Schema for fields common to all nodes.
 */
export const baseNodeSchema: RJSFSchema = {
  type: "object",
  properties: {
    label: {
      type: "string",
      title: "Node Name",
      description: "Human-readable label for this node",
    },
    description: {
      type: "string",
      title: "Description",
      description: "Optional description of what this node does",
    },
  },
};

/**
 * JSON schema representing a single conditional expression.
 */
export const conditionSchema: RJSFSchema = {
  type: "object",
  title: "Condition",
  properties: {
    left: {
      title: "Left Operand",
      description: "Left-hand operand",
      type: ["string", "number", "boolean", "null"],
    },
    operator: {
      type: "string",
      title: "Operator",
      description: "Comparison operator to evaluate",
      enum: comparisonOperatorEnum,
      default: "equals",
    },
    right: {
      title: "Right Operand",
      description: "Right-hand operand (if required)",
      type: ["string", "number", "boolean", "null"],
    },
    caseSensitive: {
      type: "boolean",
      title: "Case Sensitive",
      description: "Apply case-sensitive comparison for string operands",
      default: true,
    },
  },
  required: ["operator"],
};

/**
 * Schema for persisting variables via SetVariable nodes.
 */
export const variableSchema: RJSFSchema = {
  type: "object",
  title: "Variable",
  properties: {
    name: {
      type: "string",
      title: "Variable Name",
      description: "Name of the variable (e.g., user_name, count)",
    },
    valueType: {
      type: "string",
      title: "Type",
      description: "The type of value to store",
      enum: ["string", "number", "boolean", "object", "array"],
      default: "string",
    },
    value: {
      title: "Value",
      description: "Value to persist",
    },
  },
  required: ["name", "valueType", "value"],
  dependencies: {
    valueType: {
      oneOf: [
        {
          properties: {
            valueType: { const: "string" },
            value: { type: "string" },
          },
        },
        {
          properties: {
            valueType: { const: "number" },
            value: { type: "number" },
          },
        },
        {
          properties: {
            valueType: { const: "boolean" },
            value: { type: "boolean" },
          },
        },
        {
          properties: {
            valueType: { const: "object" },
            value: { type: "object" },
          },
        },
        {
          properties: {
            valueType: { const: "array" },
            value: { type: "array", items: {} },
          },
        },
      ],
    },
  },
};

/**
 * Schema describing an individual case branch for switch nodes.
 */
export const switchCaseSchema: RJSFSchema = {
  type: "object",
  title: "Switch Case",
  properties: {
    match: {
      title: "Match Value",
      description: "Value that activates this branch",
      oneOf: [
        { type: "string" },
        { type: "number" },
        { type: "boolean" },
        { type: "null" },
      ],
    },
    label: {
      type: "string",
      title: "Label",
      description: "Optional label used in the canvas",
    },
    branchKey: {
      type: "string",
      title: "Branch Key",
      description: "Identifier emitted when this branch is selected",
    },
    caseSensitive: {
      type: "boolean",
      title: "Case Sensitive",
      description: "Override case-sensitivity for this branch",
    },
  },
};
