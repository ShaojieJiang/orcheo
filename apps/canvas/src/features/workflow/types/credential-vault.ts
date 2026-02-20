export type CredentialVaultAccessLevel = "private" | "shared" | "public";

export type CredentialVaultHealthStatus = "healthy" | "unhealthy" | "unknown";

export interface Credential {
  id: string;
  name: string;
  provider?: string;
  /** @deprecated Use provider. */
  type?: string;
  createdAt: string;
  updatedAt: string;
  owner?: string | null;
  access: CredentialVaultAccessLevel;
  secrets?: Record<string, string>;
  status?: CredentialVaultHealthStatus;
  secretPreview?: string | null;
}

export interface CredentialInput {
  name: string;
  provider: string;
  /** @deprecated Use provider. */
  type?: string;
  access: CredentialVaultAccessLevel;
  secrets?: Record<string, string>;
  owner?: string;
}

export interface CredentialUpdateInput {
  name?: string;
  provider?: string;
  /** @deprecated Use provider. */
  type?: string;
  access?: CredentialVaultAccessLevel;
  secrets?: Record<string, string>;
}

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

export interface CredentialSecretResponse {
  id: string;
  secret: string;
}
