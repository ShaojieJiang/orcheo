import type {
  Credential,
  CredentialInput,
} from "@features/workflow/types/credential-vault";

export interface TopNavigationProps {
  currentWorkflow?: {
    name: string;
    path?: string[];
  };
  className?: string;
  credentials?: Credential[];
  isCredentialsLoading?: boolean;
  onAddCredential?: (credential: CredentialInput) => Promise<void> | void;
  onDeleteCredential?: (id: string) => Promise<void> | void;
}
