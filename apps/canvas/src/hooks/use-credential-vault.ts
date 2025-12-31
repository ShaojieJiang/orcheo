import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "@/hooks/use-toast";
import { authFetch } from "@/lib/auth-fetch";
import { buildBackendHttpUrl, getBackendBaseUrl } from "@/lib/config";
import type {
  Credential,
  CredentialInput,
  CredentialVaultEntryResponse,
} from "@features/workflow/types/credential-vault";

interface UseCredentialVaultOptions {
  actorName?: string;
  workflowId?: string | null;
}

interface UseCredentialVaultResult {
  credentials: Credential[];
  isLoading: boolean;
  onAddCredential: (credential: CredentialInput) => Promise<void>;
  onDeleteCredential: (id: string) => Promise<void>;
}

const DEFAULT_ACTOR = "system";

const mapEntryToCredential = (
  entry: CredentialVaultEntryResponse,
): Credential => ({
  id: entry.id,
  name: entry.name,
  type: entry.provider ?? entry.kind,
  createdAt: entry.created_at,
  updatedAt: entry.updated_at,
  owner: entry.owner,
  access: entry.access,
  secrets: entry.secret_preview ? { secret: entry.secret_preview } : undefined,
  status: entry.status,
});

export function useCredentialVault(
  options: UseCredentialVaultOptions = {},
): UseCredentialVaultResult {
  const { workflowId = null } = options;
  const backendBaseUrl = useMemo(() => getBackendBaseUrl(), []);
  const actorName = options.actorName?.trim() || DEFAULT_ACTOR;

  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    let isCancelled = false;

    const fetchCredentials = async () => {
      setIsLoading(true);
      try {
        const url = new URL(
          buildBackendHttpUrl("/api/credentials", backendBaseUrl),
        );
        if (workflowId) {
          url.searchParams.set("workflow_id", workflowId);
        }

        const response = await authFetch(url.toString(), {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(
            `Failed to load credentials (status ${response.status})`,
          );
        }

        const payload =
          (await response.json()) as CredentialVaultEntryResponse[];

        if (isCancelled) {
          return;
        }

        setCredentials(payload.map(mapEntryToCredential));
      } catch (error) {
        if (controller.signal.aborted || isCancelled) {
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
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    };

    void fetchCredentials();

    return () => {
      isCancelled = true;
      controller.abort();
    };
  }, [backendBaseUrl, workflowId]);

  const onAddCredential = useCallback(
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

      const response = await authFetch(
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
            actor: actorName,
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
            typeof (payload.detail as { message?: unknown }).message ===
              "string"
          ) {
            detail = (payload.detail as { message?: string }).message as string;
          }
        } catch (parseError) {
          console.warn("Failed to parse credential creation error", parseError);
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

      setCredentials((previous) => {
        const withoutDuplicate = previous.filter(
          (existing) => existing.id !== credentialRecord.id,
        );
        return [...withoutDuplicate, credentialRecord];
      });

      toast({
        title: "Credential added to vault",
        description: `${credentialRecord.name} is now available for nodes that require secure access.`,
      });
    },
    [actorName, backendBaseUrl, workflowId],
  );

  const onDeleteCredential = useCallback(
    async (id: string) => {
      const url = new URL(
        buildBackendHttpUrl(`/api/credentials/${id}`, backendBaseUrl),
      );
      if (workflowId) {
        url.searchParams.set("workflow_id", workflowId);
      }

      try {
        const response = await authFetch(url.toString(), {
          method: "DELETE",
        });

        if (!response.ok && response.status !== 404) {
          throw new Error(
            `Failed to delete credential (status ${response.status})`,
          );
        }

        setCredentials((previous) =>
          previous.filter((credential) => credential.id !== id),
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
        return;
      }
    },
    [backendBaseUrl, workflowId],
  );

  return {
    credentials,
    isLoading,
    onAddCredential,
    onDeleteCredential,
  };
}

export default useCredentialVault;
