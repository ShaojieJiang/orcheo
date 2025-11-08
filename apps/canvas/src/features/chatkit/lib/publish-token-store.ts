const publishTokenStore = new Map<string, string>();

export const setPublishToken = (workflowId: string, token: string): void => {
  const trimmedId = workflowId.trim();
  const trimmedToken = token.trim();
  if (!trimmedId || !trimmedToken) {
    return;
  }
  publishTokenStore.set(trimmedId, trimmedToken);
};

export const getPublishToken = (workflowId: string): string | undefined => {
  const trimmedId = workflowId.trim();
  if (!trimmedId) {
    return undefined;
  }
  return publishTokenStore.get(trimmedId);
};

export const clearPublishToken = (workflowId: string): void => {
  const trimmedId = workflowId.trim();
  if (!trimmedId) {
    return;
  }
  publishTokenStore.delete(trimmedId);
};

export const clearAllPublishTokens = (): void => {
  publishTokenStore.clear();
};

export const hasPublishToken = (workflowId: string): boolean => {
  const trimmedId = workflowId.trim();
  if (!trimmedId) {
    return false;
  }
  return publishTokenStore.has(trimmedId);
};
