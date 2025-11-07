import { RJSFSchema } from "@rjsf/utils";

import {
  baseNodeSchema,
  conditionSchema,
  switchCaseSchema,
} from "@features/workflow/lib/node-schemas/base";

export const logicNodeSchemas: Record<string, RJSFSchema> = {
  IfElseNode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      conditions: {
        type: "array",
        title: "Conditions",
        description: "Collection of conditions that control branching",
        items: conditionSchema,
        minItems: 1,
        default: [
          {
            left: true,
            operator: "is_truthy",
            right: null,
            caseSensitive: true,
          },
        ],
      },
      conditionLogic: {
        type: "string",
        title: "Condition Logic",
        description: "Combine conditions using logical AND/OR semantics",
        enum: ["and", "or"],
        default: "and",
      },
    },
    required: ["conditions", "conditionLogic"],
  },

  SwitchNode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      value: {
        title: "Value",
        description: "Value to inspect for routing decisions",
        oneOf: [
          { type: "string" },
          { type: "number" },
          { type: "boolean" },
          { type: "object" },
        ],
      },
      caseSensitive: {
        type: "boolean",
        title: "Case Sensitive",
        description: "Preserve case when deriving branch keys",
        default: true,
      },
      defaultBranchKey: {
        type: "string",
        title: "Default Branch Key",
        description: "Branch identifier returned when no cases match",
        default: "default",
      },
      cases: {
        type: "array",
        title: "Cases",
        description: "Collection of matchable branches",
        items: switchCaseSchema,
        minItems: 1,
      },
    },
    required: ["value", "cases"],
  },

  WhileNode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      conditions: {
        type: "array",
        title: "Loop Conditions",
        description: "Collection of conditions that control continuation",
        items: conditionSchema,
        minItems: 1,
        default: [
          {
            operator: "less_than",
            caseSensitive: true,
          },
        ],
      },
      conditionLogic: {
        type: "string",
        title: "Condition Logic",
        description: "Combine conditions using logical AND/OR semantics",
        enum: ["and", "or"],
        default: "and",
      },
      maxIterations: {
        type: "integer",
        title: "Max Iterations",
        description: "Optional guard to stop after this many iterations",
        minimum: 1,
      },
    },
    required: ["conditions", "conditionLogic"],
  },
};
