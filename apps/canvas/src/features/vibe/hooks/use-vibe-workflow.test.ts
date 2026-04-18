import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ExternalAgentProviderStatus } from "@/lib/api";
import type { StoredWorkflow } from "@features/workflow/lib/workflow-storage.types";
import { useVibeWorkflow } from "./use-vibe-workflow";
import {
  createWorkflowFromTemplate,
  listWorkflows,
} from "@features/workflow/lib/workflow-storage";
import {
  fetchWorkflowVersions,
  request,
} from "@features/workflow/lib/workflow-storage-api";

vi.mock("@features/workflow/lib/workflow-storage", () => ({
  createWorkflowFromTemplate: vi.fn(),
  listWorkflows: vi.fn(),
}));

vi.mock("@features/workflow/lib/workflow-storage-api", () => ({
  fetchWorkflowVersions: vi.fn(),
  request: vi.fn(),
}));

const READY_PROVIDER: ExternalAgentProviderStatus = {
  provider: "codex",
  display_name: "Codex",
  state: "ready",
  installed: true,
  authenticated: true,
  supports_oauth: false,
  resolved_version: "1.0.0",
  executable_path: "/usr/local/bin/codex",
  checked_at: "2026-04-13T09:00:00.000Z",
  last_auth_ok_at: "2026-04-13T09:00:00.000Z",
  detail: null,
  active_session_id: null,
};

const EXISTING_VIBE_WORKFLOW: StoredWorkflow = {
  id: "workflow-1",
  name: "Orcheo Vibe",
  description: "Managed sidebar workflow.",
  createdAt: "2026-04-13T09:00:00.000Z",
  updatedAt: "2026-04-13T09:00:00.000Z",
  owner: {
    id: "canvas-app",
    name: "canvas-app",
    avatar: "",
  },
  tags: ["orcheo-vibe-agent", "external-agent"],
  nodes: [],
  edges: [],
  versions: [],
};

describe("useVibeWorkflow", () => {
  it("re-ingests and updates an existing vibe workflow when the stored template version is outdated, without creating a new workflow", async () => {
    vi.mocked(createWorkflowFromTemplate).mockResolvedValue(undefined);
    vi.mocked(listWorkflows).mockResolvedValue([EXISTING_VIBE_WORKFLOW]);
    vi.mocked(fetchWorkflowVersions).mockResolvedValue([
      {
        id: "workflow-1-version-1",
        workflow_id: "workflow-1",
        version: 1,
        metadata: {
          source: "canvas-template",
          template_id: "template-vibe-agent",
        },
        notes: "Seeded from the Orcheo Vibe template.",
        created_by: "canvas-app",
        created_at: "2026-04-13T09:00:00.000Z",
        updated_at: "2026-04-13T09:00:00.000Z",
        graph: {},
      },
    ]);
    vi.mocked(request).mockImplementation(async (path, options) => {
      if (
        path === "/api/workflows/workflow-1/versions/ingest" &&
        options?.method === "POST"
      ) {
        return {
          id: "workflow-1-version-2",
          workflow_id: "workflow-1",
          version: 2,
        };
      }

      if (path === "/api/workflows/workflow-1" && options?.method === "PUT") {
        return {
          id: "workflow-1",
        };
      }

      throw new Error(`Unexpected request: ${path}`);
    });

    const { result } = renderHook(() => useVibeWorkflow([READY_PROVIDER]));

    await waitFor(() => {
      expect(result.current.workflowId).toBe("workflow-1");
      expect(result.current.isProvisioning).toBe(false);
      expect(result.current.error).toBeNull();
    });

    expect(createWorkflowFromTemplate).not.toHaveBeenCalled();

    const ingestCall = vi
      .mocked(request)
      .mock.calls.find(
        ([path]) => path === "/api/workflows/workflow-1/versions/ingest",
      );

    expect(ingestCall).toBeDefined();
    const ingestBody = JSON.parse(String(ingestCall?.[1]?.body ?? "{}")) as {
      script?: string;
      metadata?: {
        template?: { templateVersion?: string };
      };
    };

    expect(ingestBody.script).toContain("Canvas context:");
    expect(ingestBody.metadata?.template?.templateVersion).toBe("1.0.1");

    expect(vi.mocked(request)).toHaveBeenCalledWith(
      "/api/workflows/workflow-1",
      {
        method: "PUT",
        body: JSON.stringify({
          actor: "canvas-app",
          chatkit: {
            supported_models: [
              {
                id: "codex",
                label: "Codex",
                default: true,
              },
            ],
          },
        }),
      },
    );
  });
});
