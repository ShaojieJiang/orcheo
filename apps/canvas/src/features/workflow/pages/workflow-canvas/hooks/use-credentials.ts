import { useCallback, useEffect, useState } from "react";

import { buildBackendHttpUrl } from "@/lib/config";
import { toast } from "@/hooks/use-toast";
import type {
  Credential,
  CredentialInput,
  CredentialVaultEntryResponse,
} from "@features/workflow/types/credential-vault";

interface UseCredentialManagerOptions {
  workflowId: string | null;
  backendBaseUrl: string;
  userName: string;
}

export const useCredentialManager = ({
  workflowId,
  backendBaseUrl,
  userName,
}: UseCredentialManagerOptions) => {
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [isCredentialsLoading, setIsCredentialsLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    let isActive = true;

    const fetchCredentials = async () => {
      if (!isActive) {
        return;
      }

      setIsCredentialsLoading(true);
      try {
        const url = new URL(buildBackendHttpUrl("/api/credentials"));
        if (workflowId) {
          url.searchParams.set("workflow_id", workflowId);
        }

        const response = await fetch(url.toString(), {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Failed to load credentials (status ${response.status})`);
        }

        const payload = (await response.json()) as CredentialVaultEntryResponse[];

        if (!isActive) {
          return;
        }

        const mapped = payload.map<Credential>((entry) => ({
          id: entry.id,
          name: entry.name,
          type: entry.provider ?? entry.kind,
          createdAt: entry.created_at,
          updatedAt: entry.updated_at,
          owner: entry.owner ?? null,
          access: entry.access,
          secrets: entry.secret_preview ? { secret: entry.secret_preview } : undefined,
          status: entry.status,
        }));

        setCredentials((previous) => {
          const remoteIds = new Set(mapped.map((item) => item.id));
          const localOnly = previous.filter((item) => !remoteIds.has(item.id));
          return [...mapped, ...localOnly];
        });
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }

        console.error("Failed to load credential vault", error);
        toast({
          title: "Unable to load credentials",
          description:
            error instanceof Error
              ? error.message
              : "An unexpected error occurred while loading credentials.",
          variant: "destructive",
        });
      } finally {
        if (isActive) {
          setIsCredentialsLoading(false);
        }
      }
    };

    fetchCredentials();

    return () => {
      isActive = false;
      controller.abort();
    };
  }, [workflowId]);

  const handleAddCredential = useCallback(
    async (credential: CredentialInput) => {
      const secret = credential.secrets?.apiKey?.trim();
      if (!secret) {
        const message = "API key is required to save a credential.";
        toast({
          title: "Missing credential secret",
          description: message,
          variant: "destructive",
        });
        throw new Error(message);
      }

      const response = await fetch(
        buildBackendHttpUrl("/api/credentials", backendBaseUrl),
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            name: credential.name,
            provider: credential.type ?? "custom",
            secret,
            actor: userName,
            access: credential.access,
            workflow_id: workflowId,
            scopes: [],
          }),
        },
      );

      if (!response.ok) {
        let detail = `Failed to save credential (status ${response.status})`;
        try {
          const payload = (await response.json()) as { detail?: unknown };
          if (typeof payload?.detail === "string") {
            detail = payload.detail;
          } else if (
            payload?.detail &&
            typeof (payload.detail as { message?: unknown }).message === "string"
          ) {
            detail = (payload.detail as { message?: string }).message as string;
          }
        } catch (error) {
          console.warn("Failed to parse credential creation error", error);
        }

        toast({
          title: "Unable to save credential",
          description: detail,
          variant: "destructive",
        });
        throw new Error(detail);
      }

      const payload = (await response.json()) as CredentialVaultEntryResponse;

      const credentialRecord: Credential = {
        id: payload.id,
        name: payload.name,
        type: payload.provider ?? payload.kind,
        createdAt: payload.created_at,
        updatedAt: payload.updated_at,
        owner: payload.owner,
        access: payload.access,
        secrets: credential.secrets,
        status: payload.status,
      };

      setCredentials((prev) => {
        const withoutDuplicate = prev.filter(
          (existing) => existing.id !== credentialRecord.id,
        );
        return [...withoutDuplicate, credentialRecord];
      });

      toast({
        title: "Credential added to vault",
        description: `${credentialRecord.name} is now available for nodes that require secure access.`,
      });
    },
    [backendBaseUrl, workflowId, userName],
  );

  const handleDeleteCredential = useCallback(
    async (id: string) => {
      const url = new URL(
        buildBackendHttpUrl(`/api/credentials/${id}`, backendBaseUrl),
      );
      if (workflowId) {
        url.searchParams.set("workflow_id", workflowId);
      }

      try {
        const response = await fetch(url.toString(), {
          method: "DELETE",
        });

        if (!response.ok && response.status !== 404) {
          throw new Error(`Failed to delete credential (status ${response.status})`);
        }

        setCredentials((prev) =>
          prev.filter((credential) => credential.id !== id),
        );
        toast({
          title: "Credential removed",
          description:
            "Nodes referencing this credential will require reconfiguration before publish.",
        });
      } catch (error) {
        console.error("Failed to delete credential", error);
        const message =
          error instanceof Error ? error.message : "Credential removal failed.";
        toast({
          title: "Unable to delete credential",
          description: message,
          variant: "destructive",
        });
      }
    },
    [backendBaseUrl, workflowId],
  );

  return {
    credentials,
    isCredentialsLoading,
    handleAddCredential,
    handleDeleteCredential,
  } as const;
};
