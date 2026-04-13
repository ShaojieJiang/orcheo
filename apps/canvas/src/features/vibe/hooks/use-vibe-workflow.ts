import { useCallback, useEffect, useRef, useState } from "react";
import type { ExternalAgentProviderName } from "@/lib/api";
import {
  createWorkflowFromTemplate,
  listWorkflows,
} from "@features/workflow/lib/workflow-storage";
import { VIBE_AGENT_MAPPINGS, VIBE_AGENT_TAG } from "@features/vibe/constants";

interface VibeWorkflowState {
  workflowId: string | null;
  isProvisioning: boolean;
  error: string | null;
}

const cache = new Map<ExternalAgentProviderName, string>();

export function useVibeWorkflow(
  provider: ExternalAgentProviderName | null,
): VibeWorkflowState {
  const [state, setState] = useState<VibeWorkflowState>({
    workflowId: provider ? (cache.get(provider) ?? null) : null,
    isProvisioning: false,
    error: null,
  });
  const provisioningRef = useRef(false);

  const provision = useCallback(async (p: ExternalAgentProviderName) => {
    if (provisioningRef.current) return;

    const cached = cache.get(p);
    if (cached) {
      setState({ workflowId: cached, isProvisioning: false, error: null });
      return;
    }

    provisioningRef.current = true;
    setState((prev) => ({ ...prev, isProvisioning: true, error: null }));

    try {
      const mapping = VIBE_AGENT_MAPPINGS[p];
      const workflows = await listWorkflows();
      const existing = workflows.find(
        (w) =>
          w.name === mapping.workflowName && w.tags?.includes(VIBE_AGENT_TAG),
      );

      if (existing) {
        cache.set(p, existing.id);
        setState({
          workflowId: existing.id,
          isProvisioning: false,
          error: null,
        });
        return;
      }

      const created = await createWorkflowFromTemplate(mapping.templateId, {
        name: mapping.workflowName,
        tags: [VIBE_AGENT_TAG, "external-agent", p],
      });

      if (!created) {
        throw new Error(`Failed to create workflow for ${mapping.displayName}`);
      }

      cache.set(p, created.id);
      setState({ workflowId: created.id, isProvisioning: false, error: null });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to provision workflow";
      setState({ workflowId: null, isProvisioning: false, error: message });
    } finally {
      provisioningRef.current = false;
    }
  }, []);

  useEffect(() => {
    if (!provider) {
      setState({ workflowId: null, isProvisioning: false, error: null });
      return;
    }
    void provision(provider);
  }, [provider, provision]);

  return state;
}
