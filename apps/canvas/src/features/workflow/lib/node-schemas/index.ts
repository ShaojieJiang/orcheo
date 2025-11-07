import { RJSFSchema } from "@rjsf/utils";

import {
  baseNodeSchema,
  conditionSchema,
  variableSchema,
  switchCaseSchema,
} from "@features/workflow/lib/node-schemas/base";
import {
  ConditionOperatorGroup,
  ConditionOperatorOption,
  comparisonOperatorEnum,
  conditionOperatorGroups,
} from "@features/workflow/lib/node-schemas/condition-operators";
import { aiNodeSchemas } from "@features/workflow/lib/node-schemas/ai-nodes";
import { integrationNodeSchemas } from "@features/workflow/lib/node-schemas/integration-nodes";
import { logicNodeSchemas } from "@features/workflow/lib/node-schemas/logic-nodes";
import { nodeUiSchemas } from "@features/workflow/lib/node-schemas/ui";
import { stateNodeSchemas } from "@features/workflow/lib/node-schemas/state-nodes";
import { triggerNodeSchemas } from "@features/workflow/lib/node-schemas/trigger-nodes";

const nodeSchemaGroups: Record<string, RJSFSchema>[] = [
  logicNodeSchemas,
  stateNodeSchemas,
  aiNodeSchemas,
  integrationNodeSchemas,
  triggerNodeSchemas,
];

export const nodeSchemas: Record<string, RJSFSchema> = nodeSchemaGroups.reduce(
  (accumulator, schemaGroup) => ({
    ...accumulator,
    ...schemaGroup,
  }),
  {
    default: {
      ...baseNodeSchema,
    },
  } satisfies Record<string, RJSFSchema>,
);

export const getNodeSchema = (
  backendType: string | null | undefined,
): RJSFSchema => {
  if (!backendType) {
    return nodeSchemas.default;
  }
  return nodeSchemas[backendType] || nodeSchemas.default;
};

export const getNodeUiSchema = (
  backendType: string | null | undefined,
): Record<string, unknown> => {
  if (!backendType) {
    return nodeUiSchemas.default;
  }

  return {
    ...nodeUiSchemas.default,
    ...(nodeUiSchemas[backendType] || {}),
  };
};

export {
  baseNodeSchema,
  conditionSchema,
  variableSchema,
  switchCaseSchema,
  conditionOperatorGroups,
  comparisonOperatorEnum,
};
export type { ConditionOperatorGroup, ConditionOperatorOption };
export { nodeUiSchemas };
