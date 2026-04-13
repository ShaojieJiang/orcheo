import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { ExternalAgentProviderName } from "@/lib/api";
import { usePageContext } from "@/hooks/use-page-context";
import { useVibeAgents } from "@features/vibe/hooks/use-vibe-agents";
import { useVibeWorkflow } from "@features/vibe/hooks/use-vibe-workflow";
import { useVibeContextString } from "@features/vibe/hooks/use-vibe-context-string";
import { VibeContext } from "./vibe-context";

export function VibeProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedProvider, setSelectedProvider] =
    useState<ExternalAgentProviderName | null>(null);

  const { readyProviders } = useVibeAgents();
  const { pageContext } = usePageContext();
  const contextString = useVibeContextString(pageContext);

  // Auto-select first ready provider when none is selected or current is lost.
  useEffect(() => {
    if (readyProviders.length === 0) {
      setSelectedProvider(null);
      return;
    }

    const currentStillReady = readyProviders.some(
      (p) => p.provider === selectedProvider,
    );
    if (!currentStillReady) {
      setSelectedProvider(readyProviders[0].provider);
    }
  }, [readyProviders, selectedProvider]);

  const { workflowId: agentWorkflowId, isProvisioning } =
    useVibeWorkflow(selectedProvider);

  const toggleOpen = useCallback(() => {
    setIsOpen((prev) => !prev);
  }, []);

  const value = useMemo(
    () => ({
      isOpen,
      toggleOpen,
      selectedProvider,
      setSelectedProvider,
      readyProviders,
      agentWorkflowId,
      isProvisioning,
      contextString,
    }),
    [
      isOpen,
      toggleOpen,
      selectedProvider,
      readyProviders,
      agentWorkflowId,
      isProvisioning,
      contextString,
    ],
  );

  return <VibeContext.Provider value={value}>{children}</VibeContext.Provider>;
}
