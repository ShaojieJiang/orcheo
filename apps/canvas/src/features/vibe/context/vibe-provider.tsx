import { useCallback, useMemo, useState, type ReactNode } from "react";
import { usePageContext } from "@/hooks/use-page-context";
import { useVibeAgents } from "@features/vibe/hooks/use-vibe-agents";
import { useVibeWorkflow } from "@features/vibe/hooks/use-vibe-workflow";
import { useVibeContextString } from "@features/vibe/hooks/use-vibe-context-string";
import { VibeContext } from "./vibe-context";

export function VibeProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const { readyProviders } = useVibeAgents();
  const { pageContext } = usePageContext();
  const contextString = useVibeContextString(pageContext);
  const { workflowId: agentWorkflowId, isProvisioning } =
    useVibeWorkflow(readyProviders);

  const toggleOpen = useCallback(() => {
    setIsOpen((prev) => !prev);
  }, []);

  const value = useMemo(
    () => ({
      isOpen,
      toggleOpen,
      readyProviders,
      agentWorkflowId,
      isProvisioning,
      contextString,
    }),
    [
      isOpen,
      toggleOpen,
      readyProviders,
      agentWorkflowId,
      isProvisioning,
      contextString,
    ],
  );

  return <VibeContext.Provider value={value}>{children}</VibeContext.Provider>;
}
