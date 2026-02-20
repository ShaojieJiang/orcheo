import React, { useMemo, useState } from "react";
import { Input } from "@/design-system/ui/input";
import { Search } from "lucide-react";
import type {
  Credential,
  CredentialInput,
} from "@features/workflow/types/credential-vault";
import { AddCredentialDialog } from "./add-credential-dialog";
import { CredentialsTable } from "./credentials-table";

interface CredentialsVaultProps {
  credentials?: Credential[];
  isLoading?: boolean;
  onAddCredential?: (credential: CredentialInput) => Promise<void> | void;
  onDeleteCredential?: (id: string) => Promise<void> | void;
  className?: string;
}

export default function CredentialsVault({
  credentials = [],
  isLoading = false,
  onAddCredential,
  onDeleteCredential,
  className,
}: CredentialsVaultProps) {
  const [searchQuery, setSearchQuery] = useState("");

  const containerClassName = useMemo(
    () =>
      ["min-w-0 space-y-4", className]
        .filter((value): value is string => Boolean(value && value.trim()))
        .join(" "),
    [className],
  );

  return (
    <div className={containerClassName}>
      <div className="flex flex-wrap items-center justify-between gap-3 pr-10">
        <h2 className="text-xl font-bold">Credential Vault</h2>
        <AddCredentialDialog onAddCredential={onAddCredential} />
      </div>

      <div className="flex min-w-0 items-center">
        <div className="relative min-w-0 flex-1">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search credentials..."
            className="pl-8"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
          />
        </div>
      </div>

      <CredentialsTable
        credentials={credentials}
        isLoading={isLoading}
        searchQuery={searchQuery}
        onDeleteCredential={onDeleteCredential}
      />
    </div>
  );
}
