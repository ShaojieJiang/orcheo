const publishTokenStore = new Map<string, string>();

export const rememberPublishToken = (
  workflowId: string,
  token: string,
): void => {
  if (!workflowId || !token) {
    return;
  }
  publishTokenStore.set(workflowId, token);
};

export const readPublishToken = (workflowId: string): string | null => {
  if (!workflowId) {
    return null;
  }
  return publishTokenStore.get(workflowId) ?? null;
};

export const clearPublishToken = (workflowId: string): void => {
  if (!workflowId) {
    return;
  }
  publishTokenStore.delete(workflowId);
};

export const resetPublishTokens = (): void => {
  publishTokenStore.clear();
};
