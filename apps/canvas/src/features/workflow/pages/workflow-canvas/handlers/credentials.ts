import type React from "react";

import { buildBackendHttpUrl } from "@/lib/config";
import { toast } from "@/hooks/use-toast";
import type {
  Credential,
  CredentialInput,
  CredentialVaultEntryResponse,
} from "@features/workflow/types/credential-vault";

type AddCredentialDependencies = {
  backendBaseUrl: string | null;
  currentWorkflowId: string | null;
  userName: string;
  setCredentials: React.Dispatch<React.SetStateAction<Credential[]>>;
};

type DeleteCredentialDependencies = {
  backendBaseUrl: string | null;
  currentWorkflowId: string | null;
  setCredentials: React.Dispatch<React.SetStateAction<Credential[]>>;
};

export const createHandleAddCredential =
  ({
    backendBaseUrl,
    currentWorkflowId,
    userName,
    setCredentials,
  }: AddCredentialDependencies) =>
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
          workflow_id: currentWorkflowId,
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
  };

export const createHandleDeleteCredential =
  ({
    backendBaseUrl,
    currentWorkflowId,
    setCredentials,
  }: DeleteCredentialDependencies) =>
  async (id: string) => {
    const url = new URL(
      buildBackendHttpUrl(`/api/credentials/${id}`, backendBaseUrl),
    );
    if (currentWorkflowId) {
      url.searchParams.set("workflow_id", currentWorkflowId);
    }

    try {
      const response = await fetch(url.toString(), {
        method: "DELETE",
      });

      if (!response.ok && response.status !== 404) {
        throw new Error(
          `Failed to delete credential (status ${response.status})`,
        );
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
      toast({
        title: "Unable to delete credential",
        description:
          error instanceof Error
            ? error.message
            : "An unexpected error occurred while removing the credential.",
        variant: "destructive",
      });
      throw error;
    }
  };
