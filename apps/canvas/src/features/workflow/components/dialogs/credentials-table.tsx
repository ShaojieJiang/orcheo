import React, { useMemo, useState } from "react";
import { Badge } from "@/design-system/ui/badge";
import { Button } from "@/design-system/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/design-system/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/design-system/ui/table";
import {
  Copy,
  Edit,
  Eye,
  EyeOff,
  Key,
  Loader2,
  MoreHorizontal,
  Trash,
} from "lucide-react";
import type { Credential } from "@features/workflow/types/credential-vault";
import { CredentialAccessBadge } from "./credential-access-badge";
import { CredentialStatusBadge } from "./credential-status-badge";

interface CredentialsTableProps {
  credentials: Credential[];
  isLoading?: boolean;
  searchQuery: string;
  onDeleteCredential?: (id: string) => Promise<void> | void;
}

const SECRET_PLACEHOLDER = "••••••••••••••••";

export function CredentialsTable({
  credentials,
  isLoading,
  searchQuery,
  onDeleteCredential,
}: CredentialsTableProps) {
  const [visibleSecrets, setVisibleSecrets] = useState<Record<string, boolean>>(
    {},
  );

  const filteredCredentials = useMemo(() => {
    if (!searchQuery) {
      return credentials;
    }
    const normalizedQuery = searchQuery.toLowerCase();
    return credentials.filter((credential) => {
      const type = credential.type?.toLowerCase() ?? "";
      return (
        credential.name.toLowerCase().includes(normalizedQuery) ||
        type.includes(normalizedQuery)
      );
    });
  }, [credentials, searchQuery]);

  const toggleSecretVisibility = (credentialId: string) => {
    setVisibleSecrets((prev) => ({
      ...prev,
      [credentialId]: !prev[credentialId],
    }));
  };

  const copySecret = async (credential: Credential) => {
    const secret = credential.secrets
      ? Object.values(credential.secrets)[0]
      : undefined;
    if (!secret || typeof navigator === "undefined") {
      return;
    }
    await navigator.clipboard.writeText(secret);
  };

  return (
    <div className="min-w-0 overflow-hidden rounded-md border">
      <Table className="min-w-[900px]">
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Access</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Secret</TableHead>
            <TableHead className="whitespace-nowrap">Last Updated</TableHead>
            <TableHead className="w-[80px]" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <TableRow>
              <TableCell colSpan={7} className="py-6 text-center">
                <div className="flex items-center justify-center gap-2 text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading credentials...
                </div>
              </TableCell>
            </TableRow>
          ) : null}
          {!isLoading && filteredCredentials.length === 0 ? (
            <TableRow>
              <TableCell colSpan={7} className="text-center py-8">
                <div className="text-muted-foreground">
                  No credentials found
                  {searchQuery ? (
                    <p className="text-sm">Try adjusting your search query</p>
                  ) : null}
                </div>
              </TableCell>
            </TableRow>
          ) : null}
          {!isLoading &&
            filteredCredentials.map((credential) => {
              const secret = credential.secrets
                ? Object.values(credential.secrets)[0]
                : undefined;
              const secretVisible = visibleSecrets[credential.id];
              return (
                <TableRow key={credential.id}>
                  <TableCell className="max-w-[300px] font-medium">
                    <div className="flex min-w-0 items-center gap-2">
                      <Key className="h-4 w-4 text-muted-foreground" />
                      <span className="truncate">{credential.name}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {credential.type ?? "unknown"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <CredentialAccessBadge access={credential.access} />
                  </TableCell>
                  <TableCell>
                    <CredentialStatusBadge status={credential.status} />
                  </TableCell>
                  <TableCell>
                    <div className="flex min-w-0 items-center gap-2">
                      <div className="max-w-[220px] truncate rounded bg-muted px-2 py-1 font-mono text-xs">
                        {secret
                          ? secretVisible
                            ? secret
                            : SECRET_PLACEHOLDER
                          : "Not available"}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={() => toggleSecretVisibility(credential.id)}
                        disabled={!secret}
                      >
                        {secretVisible ? (
                          <EyeOff className="h-3 w-3" />
                        ) : (
                          <Eye className="h-3 w-3" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={() => secret && copySecret(credential)}
                        disabled={!secret}
                      >
                        <Copy className="h-3 w-3" />
                      </Button>
                    </div>
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    {new Date(credential.updatedAt).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
                    <CredentialActionsMenu
                      credentialId={credential.id}
                      onDeleteCredential={onDeleteCredential}
                    />
                  </TableCell>
                </TableRow>
              );
            })}
        </TableBody>
      </Table>
    </div>
  );
}

interface CredentialActionsMenuProps {
  credentialId: string;
  onDeleteCredential?: (id: string) => Promise<void> | void;
}

function CredentialActionsMenu({
  credentialId,
  onDeleteCredential,
}: CredentialActionsMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="h-8 w-8">
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Actions</DropdownMenuLabel>
        <DropdownMenuItem>
          <Edit className="h-4 w-4 mr-2" />
          Edit
        </DropdownMenuItem>
        <DropdownMenuItem>
          <Copy className="h-4 w-4 mr-2" />
          Duplicate
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="text-destructive focus:text-destructive"
          onClick={() => onDeleteCredential && onDeleteCredential(credentialId)}
        >
          <Trash className="h-4 w-4 mr-2" />
          Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
