import { RJSFSchema } from "@rjsf/utils";

import {
  baseNodeSchema,
  variableSchema,
} from "@features/workflow/lib/node-schemas/base";

export const stateNodeSchemas: Record<string, RJSFSchema> = {
  SetVariableNode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      variables: {
        type: "array",
        title: "Variables",
        description: "Collection of variables to store",
        items: variableSchema,
        minItems: 1,
        default: [
          {
            name: "my_variable",
            valueType: "string",
            value: "",
          },
        ],
      },
    },
    required: ["variables"],
  },

  DelayNode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      durationSeconds: {
        type: "number",
        title: "Duration (seconds)",
        description: "Duration of the pause expressed in seconds",
        minimum: 0,
        default: 0,
      },
    },
    required: ["durationSeconds"],
  },
};
