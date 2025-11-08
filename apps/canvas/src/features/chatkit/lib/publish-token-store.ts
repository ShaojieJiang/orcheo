const tokenStore = new Map<string, string>();

export const storePublishToken = (workflowId: string, token: string): void => {
  const trimmedWorkflowId = workflowId.trim();
  const trimmedToken = token.trim();
  if (!trimmedWorkflowId || !trimmedToken) {
    return;
  }
  tokenStore.set(trimmedWorkflowId, trimmedToken);
};

export const getPublishToken = (workflowId: string): string | null => {
  const trimmedWorkflowId = workflowId.trim();
  if (!trimmedWorkflowId) {
    return null;
  }
  return tokenStore.get(trimmedWorkflowId) ?? null;
};

export const clearPublishToken = (workflowId: string): void => {
  const trimmedWorkflowId = workflowId.trim();
  if (!trimmedWorkflowId) {
    return;
  }
  tokenStore.delete(trimmedWorkflowId);
};

export const resetPublishTokenStore = (): void => {
  tokenStore.clear();
};

export const getPublishTokenCount = (): number => tokenStore.size;
