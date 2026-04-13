import { createContext, useContext } from "react";
import type { ExternalAgentProviderStatus } from "@/lib/api";

export interface VibeContextValue {
  isOpen: boolean;
  toggleOpen: () => void;
  readyProviders: ExternalAgentProviderStatus[];
  agentWorkflowId: string | null;
  isProvisioning: boolean;
  contextString: string;
}

export const VibeContext = createContext<VibeContextValue>({
  isOpen: false,
  toggleOpen: () => {},
  readyProviders: [],
  agentWorkflowId: null,
  isProvisioning: false,
  contextString: "",
});

export function useVibe(): VibeContextValue {
  return useContext(VibeContext);
}
