import type { CredentialVaultEntryResponse } from "@features/workflow/types/credential-vault";

import {
  emptyResponse,
  jsonResponse,
  parseRequestBody,
} from "@/testing/mocks/backend/request-utils";

const credentialStore = new Map<string, CredentialVaultEntryResponse>();

let credentialCounter = 0;

export const handleCredentialRequest = async (
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
