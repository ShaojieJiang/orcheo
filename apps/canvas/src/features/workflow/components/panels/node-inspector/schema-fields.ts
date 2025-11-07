import type { SchemaField } from "./types";

export function buildSchemaFields(
  upstreamOutputs: Record<string, unknown> | undefined,
): SchemaField[] {
  const fields: SchemaField[] = [];

  if (!upstreamOutputs) {
    return fields;
  }

  const processValue = (value: unknown, name: string, path: string): void => {
    const valueType = Array.isArray(value)
      ? "array"
      : value === null
        ? "null"
        : typeof value;

    fields.push({
      name,
      type: valueType,
      path,
    });

    if (valueType === "object" && value !== null) {
      for (const [key, childValue] of Object.entries(
        value as Record<string, unknown>,
      )) {
        processValue(childValue, key, `${path}.${key}`);
      }
    }
  };

  for (const [nodeId, output] of Object.entries(upstreamOutputs)) {
    processValue(output, nodeId, nodeId);
  }

  return fields;
}
