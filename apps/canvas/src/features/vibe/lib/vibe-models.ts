import type { ModelOption } from "@openai/chatkit";
import type { ExternalAgentProviderStatus } from "@/lib/api";
import type { ChatKitSupportedModel } from "@features/workflow/lib/workflow-storage.types";

export const sortVibeProviders = (
  providers: ExternalAgentProviderStatus[],
): ExternalAgentProviderStatus[] => [...providers];

export const getDefaultVibeProvider = (
  providers: ExternalAgentProviderStatus[],
): ExternalAgentProviderStatus | null => {
  const [firstProvider] = sortVibeProviders(providers);
  return firstProvider ?? null;
};

export const getDefaultVibeProviderName = (
  providers: ExternalAgentProviderStatus[],
): string => getDefaultVibeProvider(providers)?.display_name ?? "Agent";

export const buildVibeComposerModels = (
  providers: ExternalAgentProviderStatus[],
): ModelOption[] | undefined => {
  const sortedProviders = sortVibeProviders(providers);
  if (sortedProviders.length === 0) {
    return undefined;
  }

  return sortedProviders.map((provider, index) => ({
    id: provider.provider,
    label: provider.display_name,
    ...(index === 0 ? { default: true } : {}),
  }));
};

export const buildVibeSupportedModels = (
  providers: ExternalAgentProviderStatus[],
): ChatKitSupportedModel[] | undefined => {
  const sortedProviders = sortVibeProviders(providers);
  if (sortedProviders.length === 0) {
    return undefined;
  }

  return sortedProviders.map((provider, index) => ({
    id: provider.provider,
    label: provider.display_name,
    ...(index === 0 ? { default: true } : {}),
  }));
};
