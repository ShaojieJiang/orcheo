import { createContext, useContext } from "react";
import type {
  ExternalAgentProviderName,
  ExternalAgentProviderStatus,
} from "@/lib/api";

export interface VibeContextValue {
  isOpen: boolean;
  toggleOpen: () => void;
  selectedProvider: ExternalAgentProviderName | null;
  setSelectedProvider: (provider: ExternalAgentProviderName) => void;
  readyProviders: ExternalAgentProviderStatus[];
  agentWorkflowId: string | null;
  isProvisioning: boolean;
  contextString: string;
}

export const VibeContext = createContext<VibeContextValue>({
  isOpen: false,
  toggleOpen: () => {},
  selectedProvider: null,
  setSelectedProvider: () => {},
  readyProviders: [],
  agentWorkflowId: null,
  isProvisioning: false,
  contextString: "",
});

export function useVibe(): VibeContextValue {
  return useContext(VibeContext);
}
