import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ExternalAgentProviderStatus } from "@/lib/api";
import { getWorkflowTemplateDefinition } from "@features/workflow/data/workflow-data";
import {
  createWorkflowFromTemplate,
  listWorkflows,
} from "@features/workflow/lib/workflow-storage";
import {
  fetchWorkflowVersions,
  request,
} from "@features/workflow/lib/workflow-storage-api";
import { type ChatKitSupportedModel } from "@features/workflow/lib/workflow-storage.types";
import {
  VIBE_AGENT_TAG,
  VIBE_WORKFLOW_NAME,
  VIBE_WORKFLOW_TEMPLATE_ID,
} from "@features/vibe/constants";
import { buildVibeSupportedModels } from "@features/vibe/lib/vibe-models";

const VIBE_TEMPLATE = getWorkflowTemplateDefinition(VIBE_WORKFLOW_TEMPLATE_ID);
const TEMPLATE_SYNC_ACTOR = "canvas-app";
const TEMPLATE_SUMMARY = { added: 0, removed: 0, modified: 0 };

interface VibeWorkflowState {
  workflowId: string | null;
  isProvisioning: boolean;
  error: string | null;
}

let cachedWorkflowId: string | null = null;

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : null;

const resolveTemplateVersion = (metadata: unknown): string | null => {
  const template = asRecord(asRecord(metadata)?.template);
  const version = template?.templateVersion;
  return typeof version === "string" && version.trim() ? version : null;
};

const resolveTemplateId = (metadata: unknown): string | null => {
  const templateId = asRecord(metadata)?.template_id;
  return typeof templateId === "string" && templateId.trim()
    ? templateId
    : null;
};

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
  const syncedTemplateRef = useRef<string | null>(null);

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

  const syncManagedTemplate = useCallback(async (workflowId: string) => {
    if (!VIBE_TEMPLATE?.metadata) {
      return;
    }

    const syncKey = `${workflowId}:${VIBE_TEMPLATE.metadata.templateVersion}`;
    if (syncedTemplateRef.current === syncKey) {
      return;
    }

    const versions = await fetchWorkflowVersions(workflowId);
    const latestMetadata = versions.at(-1)?.metadata;
    const currentTemplateId = resolveTemplateId(latestMetadata);
    const currentTemplateVersion = resolveTemplateVersion(latestMetadata);

    if (
      currentTemplateId === VIBE_WORKFLOW_TEMPLATE_ID &&
      currentTemplateVersion === VIBE_TEMPLATE.metadata.templateVersion
    ) {
      syncedTemplateRef.current = syncKey;
      return;
    }

    await request(`/api/workflows/${workflowId}/versions/ingest`, {
      method: "POST",
      body: JSON.stringify({
        script: VIBE_TEMPLATE.script,
        entrypoint: VIBE_TEMPLATE.entrypoint ?? null,
        runnable_config: VIBE_TEMPLATE.runnableConfig ?? null,
        metadata: {
          source: "canvas-template",
          template_id: VIBE_TEMPLATE.workflow.id,
          template: VIBE_TEMPLATE.metadata,
          canvas: {
            snapshot: {
              name: VIBE_TEMPLATE.workflow.name,
              description: VIBE_TEMPLATE.workflow.description,
              nodes: VIBE_TEMPLATE.workflow.nodes,
              edges: VIBE_TEMPLATE.workflow.edges,
            },
            summary: TEMPLATE_SUMMARY,
          },
        },
        notes: VIBE_TEMPLATE.notes,
        created_by: TEMPLATE_SYNC_ACTOR,
      }),
    });

    syncedTemplateRef.current = syncKey;
  }, []);

  const provision = useCallback(
    async (models: ChatKitSupportedModel[]) => {
      if (provisioningRef.current) return;

      if (cachedWorkflowId) {
        await syncManagedTemplate(cachedWorkflowId);
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
          await syncManagedTemplate(existing.id);
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
    [setWorkflowState, syncManagedTemplate, syncSupportedModels],
  );

  useEffect(() => {
    if (!supportedModels || supportedModels.length === 0) {
      syncedModelsRef.current = null;
      syncedTemplateRef.current = null;
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
