import { vi } from "vitest";
import { SAMPLE_WORKFLOWS } from "@features/workflow/data/workflow-data";
import type { CredentialVaultEntryResponse } from "@features/workflow/types/credential-vault";

type WorkflowRecord = {
  workflow: {
    id: string;
    name: string;
    slug: string;
    description: string | null;
    tags: string[];
    is_archived: boolean;
    created_at: string;
    updated_at: string;
  };
  versions: Array<{
    id: string;
    workflow_id: string;
    version: number;
    graph: Record<string, unknown>;
    metadata: unknown;
    notes: string | null;
    created_by: string;
    created_at: string;
    updated_at: string;
  }>;
};

const workflowStore = new Map<string, WorkflowRecord>();
const credentialStore = new Map<string, CredentialVaultEntryResponse>();

let workflowCounter = 0;
let credentialCounter = 0;

const jsonResponse = (body: unknown, init: ResponseInit = {}) => {
  const headers = new Headers(init.headers ?? {});
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  return new Response(JSON.stringify(body), {
    ...init,
    headers,
  });
};

const emptyResponse = (init: ResponseInit = {}) => new Response(null, init);

const parseRequestBody = async <T>(
  request: Request,
): Promise<T | undefined> => {
  if (request.method === "GET" || request.method === "HEAD") {
    return undefined;
  }

  try {
    const text = await request.clone().text();
    if (!text) {
      return undefined;
    }
    return JSON.parse(text) as T;
  } catch {
    return undefined;
  }
};

const slugify = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");

const seedWorkflows = () => {
  if (workflowStore.size > 0) {
    return;
  }

  SAMPLE_WORKFLOWS.slice(0, 3).forEach((sample, index) => {
    const id = `mock-workflow-${index + 1}`;
    const createdAt = sample.createdAt ?? new Date().toISOString();
    const updatedAt = sample.updatedAt ?? createdAt;

    workflowStore.set(id, {
      workflow: {
        id,
        name: sample.name,
        slug: slugify(sample.name),
        description: sample.description ?? null,
        tags: [...sample.tags],
        is_archived: false,
        created_at: createdAt,
        updated_at: updatedAt,
      },
      versions: [
        {
          id: `${id}-version-1`,
          workflow_id: id,
          version: 1,
          graph: {},
          metadata: {
            canvas: {
              snapshot: {
                name: sample.name,
                description: sample.description ?? null,
                nodes: sample.nodes ?? [],
                edges: sample.edges ?? [],
              },
              summary: { added: 0, removed: 0, modified: 0 },
              message: "Initial version",
              canvasToGraph: {},
              graphToCanvas: {},
            },
          },
          notes: "Initial version",
          created_by: "canvas-app",
          created_at: updatedAt,
          updated_at: updatedAt,
        },
      ],
    });
  });

  workflowCounter = workflowStore.size;
};

const handleCredentialRequest = async (
  request: Request,
  url: URL,
): Promise<Response> => {
  if (request.method === "GET") {
    return jsonResponse(Array.from(credentialStore.values()));
  }

  if (request.method === "POST") {
    const payload = await parseRequestBody<{
      name?: string;
      provider?: string;
      secret?: string;
      actor?: string;
      access?: CredentialVaultEntryResponse["access"];
    }>(request);

    const now = new Date().toISOString();
    const id = `mock-credential-${++credentialCounter}`;
    const entry: CredentialVaultEntryResponse = {
      id,
      name: payload?.name ?? `Credential ${credentialCounter}`,
      provider: payload?.provider ?? "custom",
      kind: "secret",
      created_at: now,
      updated_at: now,
      last_rotated_at: null,
      owner: payload?.actor ?? null,
      access: payload?.access ?? "private",
      status: "healthy",
      secret_preview: payload?.secret ? "••••••" : null,
    };

    credentialStore.set(id, entry);
    return jsonResponse(entry, { status: 201 });
  }

  if (request.method === "DELETE") {
    const segments = url.pathname.split("/");
    const targetId = segments.at(-1);
    if (targetId) {
      credentialStore.delete(targetId);
    }
    return emptyResponse({ status: 204 });
  }

  return emptyResponse({ status: 405 });
};

const handleWorkflowRequest = async (
  request: Request,
  url: URL,
): Promise<Response> => {
  const segments = url.pathname.split("/").filter(Boolean);
  const method = request.method.toUpperCase();

  if (segments.length === 2) {
    if (method === "GET") {
      return jsonResponse(
        Array.from(workflowStore.values()).map((entry) => entry.workflow),
      );
    }

    if (method === "POST") {
      const payload = await parseRequestBody<{
        name?: string;
        description?: string | null;
        tags?: string[];
        actor?: string;
      }>(request);

      const now = new Date().toISOString();
      const id = `mock-workflow-${++workflowCounter}`;

      const workflow: WorkflowRecord["workflow"] = {
        id,
        name: payload?.name ?? `Workflow ${workflowCounter}`,
        slug: slugify(payload?.name ?? `Workflow ${workflowCounter}`),
        description: payload?.description ?? null,
        tags: payload?.tags ?? [],
        is_archived: false,
        created_at: now,
        updated_at: now,
      };

      workflowStore.set(id, {
        workflow,
        versions: [],
      });

      return jsonResponse(workflow, { status: 201 });
    }
  }

  if (segments.length >= 3) {
    const workflowId = segments[2];
    const record = workflowStore.get(workflowId);

    if (!record) {
      return jsonResponse(
        { detail: `Workflow ${workflowId} not found` },
        { status: 404 },
      );
    }

    if (segments.length === 3) {
      if (method === "GET") {
        return jsonResponse(record.workflow);
      }

      if (method === "PUT") {
        const payload = await parseRequestBody<{
          name?: string;
          description?: string | null;
          tags?: string[];
        }>(request);

        const now = new Date().toISOString();
        record.workflow = {
          ...record.workflow,
          name: payload?.name ?? record.workflow.name,
          slug: slugify(payload?.name ?? record.workflow.name),
          description:
            payload?.description !== undefined
              ? payload.description
              : record.workflow.description,
          tags: payload?.tags ?? record.workflow.tags,
          updated_at: now,
        };

        workflowStore.set(workflowId, record);
        return jsonResponse(record.workflow);
      }
    }

    if (segments.length === 4 && segments[3] === "versions") {
      if (method === "GET") {
        return jsonResponse(record.versions);
      }

      if (method === "POST") {
        const payload = await parseRequestBody<{
          graph?: Record<string, unknown>;
          metadata?: unknown;
          notes?: string | null;
          created_by?: string;
        }>(request);
        const nextVersionNumber = record.versions.length + 1;
        const now = new Date().toISOString();

        const version = {
          id: `${workflowId}-version-${nextVersionNumber}`,
          workflow_id: workflowId,
          version: nextVersionNumber,
          graph: payload?.graph ?? {},
          metadata: payload?.metadata ?? {
            canvas: {
              snapshot: {
                name: record.workflow.name,
                description: record.workflow.description,
                nodes: [],
                edges: [],
              },
              summary: { added: 0, removed: 0, modified: 0 },
              message: payload?.notes ?? null,
              canvasToGraph: {},
              graphToCanvas: {},
            },
          },
          notes: payload?.notes ?? null,
          created_by: payload?.created_by ?? "canvas-app",
          created_at: now,
          updated_at: now,
        };

        record.workflow.updated_at = now;
        record.versions.push(version);
        workflowStore.set(workflowId, record);

        return jsonResponse(version, { status: 201 });
      }
    }
  }

  return jsonResponse(
    { detail: "Not implemented in test stub" },
    { status: 404 },
  );
};

export const setupMockBackendFetch = () => {
  seedWorkflows();

  const originalFetch =
    typeof globalThis.fetch === "function"
      ? globalThis.fetch.bind(globalThis)
      : undefined;

  const backendFetch = vi.fn(
    async (
      input: Parameters<typeof fetch>[0],
      init?: Parameters<typeof fetch>[1],
    ) => {
      const request =
        input instanceof Request ? input : new Request(input, init);

      const url = new URL(request.url, "http://localhost:8000");

      if (!url.pathname.startsWith("/api/")) {
        if (originalFetch) {
          return originalFetch(input as Parameters<typeof fetch>[0], init);
        }
        return emptyResponse({ status: 501 });
      }

      if (url.pathname.startsWith("/api/credentials")) {
        return handleCredentialRequest(request, url);
      }

      if (url.pathname.startsWith("/api/workflows")) {
        return handleWorkflowRequest(request, url);
      }

      return jsonResponse({ detail: "Unhandled mock fetch" }, { status: 404 });
    },
  );

  globalThis.fetch = backendFetch as typeof fetch;
  return backendFetch;
};
