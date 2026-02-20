import type { WorkflowRunnableConfig } from "@features/workflow/lib/workflow-storage.types";

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const toPositiveInteger = (value: unknown): number | undefined => {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return undefined;
  }
  const integer = Math.floor(value);
  return integer > 0 ? integer : undefined;
};

export const toWorkflowConfig = (
  formData: Record<string, unknown>,
): WorkflowRunnableConfig | null => {
  const next: WorkflowRunnableConfig = {};

  if (
    isRecord(formData.configurable) &&
    Object.keys(formData.configurable).length > 0
  ) {
    next.configurable = formData.configurable;
  }

  if (typeof formData.run_name === "string") {
    const runName = formData.run_name.trim();
    if (runName.length > 0) {
      next.run_name = runName;
    }
  }

  if (Array.isArray(formData.tags)) {
    const tags = formData.tags
      .filter((item): item is string => typeof item === "string")
      .map((item) => item.trim())
      .filter(
        (item, index, array) =>
          item.length > 0 && array.indexOf(item) === index,
      );
    if (tags.length > 0) {
      next.tags = tags;
    }
  }

  if (
    isRecord(formData.metadata) &&
    Object.keys(formData.metadata).length > 0
  ) {
    next.metadata = formData.metadata;
  }

  if (Array.isArray(formData.callbacks) && formData.callbacks.length > 0) {
    next.callbacks = formData.callbacks;
  }

  const recursionLimit = toPositiveInteger(formData.recursion_limit);
  if (recursionLimit) {
    next.recursion_limit = recursionLimit;
  }

  const maxConcurrency = toPositiveInteger(formData.max_concurrency);
  if (maxConcurrency) {
    next.max_concurrency = maxConcurrency;
  }

  if (isRecord(formData.prompts) && Object.keys(formData.prompts).length > 0) {
    next.prompts = formData.prompts;
  }

  return Object.keys(next).length > 0 ? next : null;
};

export const toFormData = (
  config: WorkflowRunnableConfig | null,
): Record<string, unknown> => ({
  configurable: config?.configurable ?? {},
  run_name: config?.run_name ?? "",
  tags: config?.tags ?? [],
  metadata: config?.metadata ?? {},
  callbacks: config?.callbacks ?? [],
  recursion_limit: config?.recursion_limit,
  max_concurrency: config?.max_concurrency,
  prompts: config?.prompts ?? {},
});
