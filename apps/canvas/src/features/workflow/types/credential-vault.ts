export type CredentialVaultAccessLevel = "private" | "shared" | "public";

export type CredentialVaultHealthStatus = "healthy" | "unhealthy" | "unknown";

export interface Credential {
  id: string;
  name: string;
  type?: string;
  createdAt: string;
  updatedAt: string;
  owner?: string | null;
  access: CredentialVaultAccessLevel;
  secrets?: Record<string, string>;
  status?: CredentialVaultHealthStatus;
}

export type CredentialInput = Omit<
  Credential,
  "id" | "createdAt" | "updatedAt" | "owner"
> & {
  owner?: string;
};

export interface CredentialVaultEntryResponse {
  id: string;
  name: string;
  provider: string;
  kind: "secret" | "oauth";
  created_at: string;
  updated_at: string;
  last_rotated_at: string | null;
  owner: string | null;
  access: CredentialVaultAccessLevel;
  status: CredentialVaultHealthStatus;
  secret_preview?: string | null;
}
