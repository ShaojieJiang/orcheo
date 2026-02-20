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
import type {
  Credential,
  CredentialUpdateInput,
} from "@features/workflow/types/credential-vault";
import { CredentialAccessBadge } from "./credential-access-badge";
import { CredentialStatusBadge } from "./credential-status-badge";
import { EditCredentialDialog } from "./edit-credential-dialog";

interface CredentialsTableProps {
  credentials: Credential[];
  isLoading?: boolean;
  searchQuery: string;
  onUpdateCredential?: (
    id: string,
    updates: CredentialUpdateInput,
  ) => Promise<void> | void;
  onDeleteCredential?: (id: string) => Promise<void> | void;
  onRevealCredentialSecret?: (id: string) => Promise<string | null>;
}

const SECRET_PLACEHOLDER = "••••••••••••••••";
const MASKED_SECRET_MARKER = "•";

const isMaskedSecret = (value: string): boolean =>
  value.includes(MASKED_SECRET_MARKER);

const getCredentialSecretValue = (
  credential: Credential,
  loadedSecrets: Record<string, string>,
): string | undefined => {
  const loaded = loadedSecrets[credential.id];
  if (loaded) {
    return loaded;
  }
  const inlineSecret = credential.secrets
    ? Object.values(credential.secrets)[0]
    : undefined;
  if (inlineSecret && !isMaskedSecret(inlineSecret)) {
    return inlineSecret;
  }
  return undefined;
};

export function CredentialsTable({
  credentials,
  isLoading,
  searchQuery,
  onUpdateCredential,
  onDeleteCredential,
  onRevealCredentialSecret,
}: CredentialsTableProps) {
  const [visibleSecrets, setVisibleSecrets] = useState<Record<string, boolean>>(
    {},
  );
  const [loadedSecrets, setLoadedSecrets] = useState<Record<string, string>>(
    {},
  );
  const [loadingSecretState, setLoadingSecretState] = useState<
    Record<string, boolean>
  >({});
  const [editingCredential, setEditingCredential] = useState<Credential | null>(
    null,
  );

  const filteredCredentials = useMemo(() => {
    if (!searchQuery) {
      return credentials;
    }
    const normalizedQuery = searchQuery.toLowerCase();
    return credentials.filter((credential) => {
      const provider = (
        credential.provider ??
        credential.type ??
        ""
      ).toLowerCase();
      return (
        credential.name.toLowerCase().includes(normalizedQuery) ||
        provider.includes(normalizedQuery)
      );
    });
  }, [credentials, searchQuery]);

  const ensureCredentialSecret = async (
    credential: Credential,
  ): Promise<string | undefined> => {
    const existingSecret = getCredentialSecretValue(credential, loadedSecrets);
    if (existingSecret) {
      return existingSecret;
    }
    if (!onRevealCredentialSecret) {
      return undefined;
    }

    setLoadingSecretState((previous) => ({
      ...previous,
      [credential.id]: true,
    }));
    try {
      const revealed = await onRevealCredentialSecret(credential.id);
      if (!revealed) {
        return undefined;
      }
      setLoadedSecrets((previous) => ({
        ...previous,
        [credential.id]: revealed,
      }));
      return revealed;
    } finally {
      setLoadingSecretState((previous) => ({
        ...previous,
        [credential.id]: false,
      }));
    }
  };

  const toggleSecretVisibility = async (credential: Credential) => {
    const credentialId = credential.id;
    const isVisible = Boolean(visibleSecrets[credentialId]);
    if (!isVisible) {
      try {
        await ensureCredentialSecret(credential);
      } catch (error) {
        console.error("Failed to reveal credential secret", error);
        return;
      }
    }
    setVisibleSecrets((prev) => ({
      ...prev,
      [credentialId]: !prev[credentialId],
    }));
  };

  const copySecret = async (credential: Credential) => {
    let secret: string | undefined;
    try {
      secret = await ensureCredentialSecret(credential);
    } catch (error) {
      console.error("Failed to copy credential secret", error);
      return;
    }
    if (!secret || typeof navigator === "undefined") {
      return;
    }
    await navigator.clipboard.writeText(secret);
  };

  const openCredentialEditor = async (credential: Credential) => {
    try {
      const revealedSecret = await ensureCredentialSecret(credential);
      if (revealedSecret) {
        setEditingCredential({
          ...credential,
          secrets: {
            ...(credential.secrets ?? {}),
            secret: revealedSecret,
          },
        });
        return;
      }
    } catch (error) {
      console.error("Failed to load credential secret for editing", error);
    }

    setEditingCredential(credential);
  };

  return (
    <div className="min-w-0 overflow-hidden rounded-md border">
      <Table className="min-w-[900px]">
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Provider</TableHead>
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
              const inlineSecret = credential.secrets
                ? Object.values(credential.secrets)[0]
                : undefined;
              const secret = getCredentialSecretValue(
                credential,
                loadedSecrets,
              );
              const secretVisible = visibleSecrets[credential.id];
              const isLoadingSecret =
                loadingSecretState[credential.id] === true;
              const provider =
                credential.provider ?? credential.type ?? "unknown";
              const hasSecret =
                secret !== undefined ||
                inlineSecret !== undefined ||
                credential.secretPreview != null;
              const canReadSecret =
                secret !== undefined ||
                (hasSecret && onRevealCredentialSecret !== undefined);
              return (
                <TableRow key={credential.id}>
                  <TableCell className="max-w-[300px] font-medium">
                    <div className="flex min-w-0 items-center gap-2">
                      <Key className="h-4 w-4 text-muted-foreground" />
                      <span className="truncate">{credential.name}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{provider}</Badge>
                  </TableCell>
                  <TableCell>
                    <CredentialAccessBadge access={credential.access} />
                  </TableCell>
                  <TableCell>
                    <CredentialStatusBadge status={credential.status} />
                  </TableCell>
                  <TableCell>
                    <div className="flex min-w-0 items-center gap-2">
                      <div
                        className={
                          secretVisible && secret
                            ? "w-[150px] overflow-x-auto overflow-y-hidden whitespace-nowrap rounded bg-muted px-2 py-1 font-mono text-xs"
                            : "w-[150px] overflow-hidden truncate rounded bg-muted px-2 py-1 font-mono text-xs"
                        }
                      >
                        {secret
                          ? secretVisible
                            ? secret
                            : SECRET_PLACEHOLDER
                          : hasSecret
                            ? SECRET_PLACEHOLDER
                            : "Not available"}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={() => void toggleSecretVisibility(credential)}
                        disabled={!canReadSecret || isLoadingSecret}
                        aria-label={`${
                          secretVisible ? "Hide" : "Show"
                        } secret for ${credential.name}`}
                      >
                        {isLoadingSecret ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : secretVisible ? (
                          <EyeOff className="h-3 w-3" />
                        ) : (
                          <Eye className="h-3 w-3" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={() => void copySecret(credential)}
                        disabled={!canReadSecret}
                        aria-label={`Copy secret for ${credential.name}`}
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
                      canEdit={Boolean(onUpdateCredential)}
                      onEdit={() => void openCredentialEditor(credential)}
                      onDeleteCredential={onDeleteCredential}
                      credentialId={credential.id}
                      credentialName={credential.name}
                    />
                  </TableCell>
                </TableRow>
              );
            })}
        </TableBody>
      </Table>
      <EditCredentialDialog
        credential={editingCredential}
        open={editingCredential !== null}
        onOpenChange={(open) => {
          if (!open) {
            setEditingCredential(null);
          }
        }}
        onUpdateCredential={onUpdateCredential}
      />
    </div>
  );
}

interface CredentialActionsMenuProps {
  canEdit: boolean;
  onEdit: () => void;
  credentialId: string;
  credentialName: string;
  onDeleteCredential?: (id: string) => Promise<void> | void;
}

function CredentialActionsMenu({
  canEdit,
  onEdit,
  credentialId,
  credentialName,
  onDeleteCredential,
}: CredentialActionsMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          aria-label={`Credential actions for ${credentialName}`}
        >
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Actions</DropdownMenuLabel>
        <DropdownMenuItem onClick={onEdit} disabled={!canEdit}>
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
