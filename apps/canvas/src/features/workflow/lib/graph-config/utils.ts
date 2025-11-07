export const isRecord = (value: unknown): value is Record<string, unknown> => {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const prototype = Object.getPrototypeOf(value);
  return prototype === null || prototype === Object.prototype;
};

export const toStringRecord = (value: unknown): Record<string, string> => {
  if (!isRecord(value)) {
    return {};
  }

  return Object.entries(value).reduce<Record<string, string>>(
    (acc, [key, rawValue]) => {
      if (typeof key !== "string") {
        return acc;
      }

      if (typeof rawValue === "string") {
        acc[key] = rawValue;
        return acc;
      }

      if (typeof rawValue === "number" || typeof rawValue === "boolean") {
        acc[key] = String(rawValue);
        return acc;
      }

      return acc;
    },
    {},
  );
};

export const slugify = (value: string, fallback: string): string => {
  const slug = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-{2,}/g, "-");
  return slug || fallback;
};

export const ensureUniqueName = (
  candidate: string,
  used: Set<string>,
): string => {
  if (!used.has(candidate)) {
    used.add(candidate);
    return candidate;
  }
  let counter = 2;
  while (used.has(`${candidate}-${counter}`)) {
    counter += 1;
  }
  const unique = `${candidate}-${counter}`;
  used.add(unique);
  return unique;
};

export const isTemplateExpression = (value: unknown): value is string => {
  return typeof value === "string" && value.includes("{{");
};
