import type { CanvasNode, NodeData } from "./types";

const PERSISTED_NODE_FIELDS = new Set([
  "label",
  "description",
  "type",
  "isDisabled",
]);

export const DEFAULT_NODE_LABEL = "New Node";

const normaliseLabelInput = (value: unknown): string => {
  if (typeof value !== "string") {
    return "";
  }

  return value.trim();
};

export const sanitizeLabel = (
  value: unknown,
  fallback = DEFAULT_NODE_LABEL,
): string => {
  const normalised = normaliseLabelInput(value);
  return normalised.length > 0 ? normalised : fallback;
};

export const slugifyLabel = (label: string): string => {
  return label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
};

export const buildExistingNameSet = (
  nodes: CanvasNode[],
  excludeId?: string,
): Set<string> => {
  const names = new Set<string>();
  for (const node of nodes) {
    if (excludeId && node.id === excludeId) {
      continue;
    }
    const label = sanitizeLabel(
      (node.data?.label as string) ?? node.id ?? DEFAULT_NODE_LABEL,
    );
    names.add(label.toLowerCase());
  }
  return names;
};

export const buildExistingIdSet = (
  nodes: CanvasNode[],
  excludeId?: string,
): Set<string> => {
  const ids = new Set<string>();
  for (const node of nodes) {
    if (excludeId && node.id === excludeId) {
      continue;
    }
    ids.add(node.id);
  }
  return ids;
};

export const assignUniqueIdentity = (
  desiredLabel: string,
  nameSet: Set<string>,
  idSet: Set<string>,
) => {
  const baseLabel = sanitizeLabel(desiredLabel);
  let candidateLabel = baseLabel;
  let attempt = 2;
  while (nameSet.has(candidateLabel.toLowerCase())) {
    candidateLabel = `${baseLabel} (${attempt})`;
    attempt += 1;
  }
  nameSet.add(candidateLabel.toLowerCase());

  const baseSlug = slugifyLabel(candidateLabel) || "node";
  let candidateId = baseSlug;
  attempt = 2;
  while (idSet.has(candidateId)) {
    candidateId = `${baseSlug}-${attempt}`;
    attempt += 1;
  }
  idSet.add(candidateId);

  return { id: candidateId, label: candidateLabel };
};

export const createIdentityAllocator = (
  nodes: CanvasNode[],
  options: { excludeId?: string } = {},
) => {
  const nameSet = buildExistingNameSet(nodes, options.excludeId);
  const idSet = buildExistingIdSet(nodes, options.excludeId);
  return (desiredLabel: string) =>
    assignUniqueIdentity(desiredLabel, nameSet, idSet);
};

export const sanitizeNodeDataForPersist = (
  data?: NodeData,
): Record<string, unknown> => {
  const sanitized: Record<string, unknown> = {
    label:
      typeof data?.label === "string"
        ? data.label
        : data?.label !== undefined
          ? String(data.label)
          : DEFAULT_NODE_LABEL,
  };

  if (typeof data?.description === "string") {
    sanitized.description = data.description;
  }

  if (typeof data?.type === "string") {
    sanitized.type = data.type;
  }

  if (typeof data?.isDisabled === "boolean") {
    sanitized.isDisabled = data.isDisabled;
  }

  Object.entries(data ?? {}).forEach(([key, value]) => {
    if (PERSISTED_NODE_FIELDS.has(key)) {
      return;
    }

    if (
      value === null ||
      typeof value === "string" ||
      typeof value === "number" ||
      typeof value === "boolean"
    ) {
      sanitized[key] = value;
      return;
    }

    if (Array.isArray(value)) {
      sanitized[key] = value;
      return;
    }

    if (
      typeof value === "object" &&
      value !== null &&
      !(value as { $$typeof?: unknown }).$$typeof
    ) {
      sanitized[key] = value;
    }
  });

  return sanitized;
};
