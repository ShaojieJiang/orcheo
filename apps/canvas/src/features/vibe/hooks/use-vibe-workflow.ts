import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ExternalAgentProviderStatus } from "@/lib/api";
import {
  createWorkflowFromTemplate,
  listWorkflows,
} from "@features/workflow/lib/workflow-storage";
import { request } from "@features/workflow/lib/workflow-storage-api";
import {
  type ApiWorkflow,
  type ChatKitSupportedModel,
} from "@features/workflow/lib/workflow-storage.types";
import {
  VIBE_AGENT_TAG,
  VIBE_WORKFLOW_NAME,
  VIBE_WORKFLOW_TEMPLATE_ID,
} from "@features/vibe/constants";
import { buildVibeSupportedModels } from "@features/vibe/lib/vibe-models";

interface VibeWorkflowState {
  workflowId: string | null;
  isProvisioning: boolean;
  error: string | null;
}

let cachedWorkflowId: string | null = null;

export function useVibeWorkflow(
  readyProviders: ExternalAgentProviderStatus[],
): VibeWorkflowState {
  const supportedModels = useMemo(
    () => buildVibeSupportedModels(readyProviders),
    [readyProviders],
  );
  const supportedModelsSignature = useMemo(
    () => JSON.stringify(supportedModels ?? []),
    [supportedModels],
  );
  const [state, setState] = useState<VibeWorkflowState>({
    workflowId: supportedModels ? cachedWorkflowId : null,
    isProvisioning: false,
    error: null,
  });
  const provisioningRef = useRef(false);
  const syncedModelsRef = useRef<string | null>(null);

  const setWorkflowState = useCallback((nextState: VibeWorkflowState) => {
    setState((currentState) => {
      if (
        currentState.workflowId === nextState.workflowId &&
        currentState.isProvisioning === nextState.isProvisioning &&
        currentState.error === nextState.error
      ) {
        return currentState;
      }
      return nextState;
    });
  }, []);

  const syncSupportedModels = useCallback(
    async (workflowId: string, models: ChatKitSupportedModel[]) => {
      if (syncedModelsRef.current === supportedModelsSignature) {
        return;
      }

      await request<ApiWorkflow>(`/api/workflows/${workflowId}`, {
        method: "PUT",
        body: JSON.stringify({
          actor: "canvas-app",
          chatkit: {
            supported_models: models,
          },
        }),
      });

      syncedModelsRef.current = supportedModelsSignature;
    },
    [supportedModelsSignature],
  );

  const provision = useCallback(
    async (models: ChatKitSupportedModel[]) => {
      if (provisioningRef.current) return;

      if (cachedWorkflowId) {
        await syncSupportedModels(cachedWorkflowId, models);
        setWorkflowState({
          workflowId: cachedWorkflowId,
          isProvisioning: false,
          error: null,
        });
        return;
      }

      provisioningRef.current = true;
      setState((prev) => {
        if (prev.isProvisioning && prev.error === null) {
          return prev;
        }
        return { ...prev, isProvisioning: true, error: null };
      });

      try {
        const workflows = await listWorkflows();
        const existing = workflows.find(
          (workflow) =>
            workflow.name === VIBE_WORKFLOW_NAME &&
            workflow.tags?.includes(VIBE_AGENT_TAG),
        );

        if (existing) {
          cachedWorkflowId = existing.id;
          await syncSupportedModels(existing.id, models);
          setWorkflowState({
            workflowId: existing.id,
            isProvisioning: false,
            error: null,
          });
          return;
        }

        const created = await createWorkflowFromTemplate(
          VIBE_WORKFLOW_TEMPLATE_ID,
          {
            name: VIBE_WORKFLOW_NAME,
            tags: [VIBE_AGENT_TAG, "external-agent"],
          },
        );

        if (!created) {
          throw new Error("Failed to create Orcheo Vibe workflow");
        }

        cachedWorkflowId = created.id;
        await syncSupportedModels(created.id, models);
        setWorkflowState({
          workflowId: created.id,
          isProvisioning: false,
          error: null,
        });
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to provision workflow";
        setWorkflowState({
          workflowId: null,
          isProvisioning: false,
          error: message,
        });
      } finally {
        provisioningRef.current = false;
      }
    },
    [setWorkflowState, syncSupportedModels],
  );

  useEffect(() => {
    if (!supportedModels || supportedModels.length === 0) {
      syncedModelsRef.current = null;
      setWorkflowState({
        workflowId: null,
        isProvisioning: false,
        error: null,
      });
      return;
    }
    void provision(supportedModels);
  }, [provision, setWorkflowState, supportedModels, supportedModelsSignature]);

  return state;
}
