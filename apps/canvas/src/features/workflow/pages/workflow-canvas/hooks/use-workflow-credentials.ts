import { useEffect, useMemo, useState } from "react";

import { authFetch } from "@/lib/auth-fetch";
import { buildBackendHttpUrl } from "@/lib/config";
import { toast } from "@/hooks/use-toast";
import type {
  Credential,
  CredentialVaultEntryResponse,
} from "@features/workflow/types/credential-vault";

import {
  createHandleAddCredential,
  createHandleDeleteCredential,
} from "../handlers/credentials";

type UseWorkflowCredentialsArgs = {
  routeWorkflowId?: string;
  currentWorkflowId: string | null;
  backendBaseUrl: string | null;
  userName: string;
};

export const useWorkflowCredentials = ({
  routeWorkflowId,
  currentWorkflowId,
  backendBaseUrl,
  userName,
}: UseWorkflowCredentialsArgs) => {
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
        if (routeWorkflowId) {
          url.searchParams.set("workflow_id", routeWorkflowId);
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
          secrets: entry.secret_preview
            ? { secret: entry.secret_preview }
            : undefined,
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
  }, [routeWorkflowId]);

  const handleAddCredential = useMemo(
    () =>
      createHandleAddCredential({
        backendBaseUrl,
        currentWorkflowId,
        userName,
        setCredentials,
      }),
    [backendBaseUrl, currentWorkflowId, setCredentials, userName],
  );

  const handleDeleteCredential = useMemo(
    () =>
      createHandleDeleteCredential({
        backendBaseUrl,
        currentWorkflowId,
        setCredentials,
      }),
    [backendBaseUrl, currentWorkflowId, setCredentials],
  );

  return {
    credentials,
    isCredentialsLoading,
    handleAddCredential,
    handleDeleteCredential,
  };
};
