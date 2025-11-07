import {
  isRecord,
  isTemplateExpression,
} from "@features/workflow/lib/graph-config/utils";
import type { MaybeYieldFn } from "@features/workflow/lib/graph-config/types";

export const applySetVariableConfig = async (
  data: Record<string, unknown>,
  nodeConfig: Record<string, unknown>,
  warnings: string[],
  maybeYield: MaybeYieldFn,
): Promise<void> => {
  const variables = Array.isArray(data?.variables)
    ? (data.variables as Array<Record<string, unknown>>)
    : [];
  const variablesDict: Record<string, unknown> = {};

  for (const variable of variables) {
    if (!variable?.name) {
      await maybeYield();
      continue;
    }

    const variableName = String(variable.name);
    const valueType =
      typeof variable.valueType === "string" ? variable.valueType : "string";
    let typedValue = variable.value ?? null;
    const templateExpression = isTemplateExpression(typedValue);

    if (typedValue !== null && typedValue !== undefined) {
      switch (valueType) {
        case "number":
          if (typeof typedValue === "number" || templateExpression) {
            break;
          }
          {
            const parsedNumber = Number(typedValue);
            if (Number.isFinite(parsedNumber)) {
              typedValue = parsedNumber;
            } else {
              const message = `Variable "${variableName}" must be numeric. Keeping original value "${typedValue}".`;
              warnings.push(message);
              console.warn(message);
            }
          }
          break;
        case "boolean":
          if (typeof typedValue === "boolean" || templateExpression) {
            break;
          }
          if (typeof typedValue === "string") {
            const normalised = typedValue.trim().toLowerCase();
            typedValue = normalised === "true";
          } else {
            typedValue = typedValue === 1;
          }
          break;
        case "object":
          if (templateExpression) {
            break;
          }
          if (typeof typedValue === "string") {
            try {
              const parsed = JSON.parse(typedValue);
              if (isRecord(parsed)) {
                typedValue = parsed;
              } else {
                const message = `Variable "${variableName}" must be a JSON object. Using an empty object instead.`;
                warnings.push(message);
                console.warn(message);
                typedValue = {};
              }
            } catch (error) {
              const message = `Variable "${variableName}" contains invalid JSON. Using an empty object instead.`;
              warnings.push(message);
              console.warn(message, error);
              typedValue = {};
            }
          } else if (!isRecord(typedValue)) {
            const message = `Variable "${variableName}" must be an object value. Using an empty object instead.`;
            warnings.push(message);
            console.warn(message);
            typedValue = {};
          }
          break;
        case "array":
          if (templateExpression) {
            break;
          }
          if (typeof typedValue === "string") {
            try {
              const parsed = JSON.parse(typedValue);
              if (Array.isArray(parsed)) {
                typedValue = parsed;
              } else {
                const message = `Variable "${variableName}" must be a JSON array. Using an empty array instead.`;
                warnings.push(message);
                console.warn(message);
                typedValue = [];
              }
            } catch (error) {
              const message = `Variable "${variableName}" contains invalid JSON. Using an empty array instead.`;
              warnings.push(message);
              console.warn(message, error);
              typedValue = [];
            }
          } else if (!Array.isArray(typedValue)) {
            const message = `Variable "${variableName}" must be an array value. Using an empty array instead.`;
            warnings.push(message);
            console.warn(message);
            typedValue = [];
          }
          break;
        default:
          break;
      }
    }

    variablesDict[variableName] = typedValue;
    await maybeYield();
  }

  nodeConfig.variables = variablesDict;
};
