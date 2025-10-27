import React, { useState } from "react";
import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/design-system/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/design-system/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import { Badge } from "@/design-system/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/design-system/ui/dropdown-menu";
import {
  Key,
  Plus,
  MoreHorizontal,
  Copy,
  Edit,
  Trash,
  Eye,
  EyeOff,
  Search,
  Lock,
  Users,
  Shield,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Circle,
} from "lucide-react";
import type {
  Credential,
  CredentialInput,
  CredentialVaultHealthStatus,
} from "@features/workflow/types/credential-vault";

interface CredentialsVaultProps {
  credentials?: Credential[];
  isLoading?: boolean;
  onAddCredential?: (credential: CredentialInput) => Promise<void> | void;
  onDeleteCredential?: (id: string) => void;
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
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isSavingCredential, setIsSavingCredential] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [newCredential, setNewCredential] = useState<{
    name: string;
    type: string;
    access: "private" | "shared" | "public";
    secrets: Record<string, string>;
  }>({
    name: "",
    type: "api",
    access: "private",
    secrets: { apiKey: "" },
  });

  // Filter credentials based on search query
  const filteredCredentials = credentials.filter((credential) => {
    const search = searchQuery.toLowerCase();
    const type = credential.type?.toLowerCase() ?? "";
    return (
      credential.name.toLowerCase().includes(search) || type.includes(search)
    );
  });

  const toggleShowSecret = (credentialId: string) => {
    setShowSecrets((prev) => ({
      ...prev,
      [credentialId]: !prev[credentialId],
    }));
  };

  const handleAddCredential = async () => {
    if (!onAddCredential || !newCredential.name.trim()) {
      return;
    }

    setSaveError(null);
    setIsSavingCredential(true);
    try {
      await onAddCredential(newCredential);
      setNewCredential({
        name: "",
        type: "api",
        access: "private",
        secrets: { apiKey: "" },
      });
      setIsAddDialogOpen(false);
    } catch (error) {
      console.error("Failed to save credential", error);
      const message =
        error instanceof Error
          ? error.message
          : "Unable to save credential. Please try again.";
      setSaveError(message);
    } finally {
      setIsSavingCredential(false);
    }
  };

  const getAccessBadge = (access: string) => {
    switch (access) {
      case "private":
        return (
          <Badge
            variant="outline"
            className="bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-800"
          >
            <Lock className="h-3 w-3 mr-1" />
            Private
          </Badge>
        );

      case "shared":
        return (
          <Badge
            variant="outline"
            className="bg-purple-100 text-purple-800 border-purple-200 dark:bg-purple-900/30 dark:text-purple-400 dark:border-purple-800"
          >
            <Users className="h-3 w-3 mr-1" />
            Shared
          </Badge>
        );

      case "public":
        return (
          <Badge
            variant="outline"
            className="bg-green-100 text-green-800 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800"
          >
            <Shield className="h-3 w-3 mr-1" />
            Public
          </Badge>
        );

      default:
        return null;
    }
  };

  const getStatusBadge = (status: CredentialVaultHealthStatus | undefined) => {
    const normalized = status ?? "unknown";

    switch (normalized) {
      case "healthy":
        return (
          <Badge
            variant="outline"
            className="flex items-center gap-1 bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-800"
          >
            <CheckCircle2 className="h-3 w-3" />
            Healthy
          </Badge>
        );
      case "unhealthy":
        return (
          <Badge
            variant="outline"
            className="flex items-center gap-1 bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800"
          >
            <AlertTriangle className="h-3 w-3" />
            Unhealthy
          </Badge>
        );
      case "unknown":
      default:
        return (
          <Badge
            variant="outline"
            className="flex items-center gap-1 bg-muted text-muted-foreground border-border"
          >
            <Circle className="h-3 w-3" />
            Unknown
          </Badge>
        );
    }
  };

  return (
    <div className={`space-y-4 ${className}`}>
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-bold">Credential Vault</h2>
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Add Credential
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>Add New Credential</DialogTitle>
              <DialogDescription>
                Create a new credential for connecting to external services.
                Credentials are encrypted at rest.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <label
                  htmlFor="name"
                  className="text-right text-sm font-medium"
                >
                  Name
                </label>
                <Input
                  id="name"
                  value={newCredential.name}
                  onChange={(e) =>
                    setNewCredential({ ...newCredential, name: e.target.value })
                  }
                  className="col-span-3"
                  placeholder="My API Credential"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <label
                  htmlFor="type"
                  className="text-right text-sm font-medium"
                >
                  Type
                </label>
                <Select
                  value={newCredential.type}
                  onValueChange={(value) =>
                    setNewCredential({ ...newCredential, type: value })
                  }
                >
                  <SelectTrigger className="col-span-3">
                    <SelectValue placeholder="Select credential type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="api">API Key</SelectItem>
                    <SelectItem value="oauth">OAuth</SelectItem>
                    <SelectItem value="database">Database</SelectItem>
                    <SelectItem value="aws">AWS</SelectItem>
                    <SelectItem value="gcp">Google Cloud</SelectItem>
                    <SelectItem value="azure">Azure</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <label
                  htmlFor="access"
                  className="text-right text-sm font-medium"
                >
                  Access
                </label>
                <Select
                  value={newCredential.access}
                  onValueChange={(value: "private" | "shared" | "public") =>
                    setNewCredential({ ...newCredential, access: value })
                  }
                >
                  <SelectTrigger className="col-span-3">
                    <SelectValue placeholder="Select access level" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="private">Private</SelectItem>
                    <SelectItem value="shared">Shared</SelectItem>
                    <SelectItem value="public">Public</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <label
                  htmlFor="apiKey"
                  className="text-right text-sm font-medium"
                >
                  API Key
                </label>
                <Input
                  id="apiKey"
                  type="password"
                  value={newCredential.secrets.apiKey}
                  onChange={(e) =>
                    setNewCredential({
                      ...newCredential,
                      secrets: {
                        ...newCredential.secrets,
                        apiKey: e.target.value,
                      },
                    })
                  }
                  className="col-span-3"
                  placeholder="Enter API key"
                />
              </div>
            </div>
            {saveError ? (
              <p className="text-sm text-destructive px-1">{saveError}</p>
            ) : null}
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setIsAddDialogOpen(false)}
                disabled={isSavingCredential}
              >
                Cancel
              </Button>
              <Button
                onClick={handleAddCredential}
                disabled={isSavingCredential}
              >
                {isSavingCredential ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  "Save Credential"
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="flex items-center space-x-2">
        <div className="relative flex-1">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />

          <Input
            placeholder="Search credentials..."
            className="pl-8"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      <div className="border rounded-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Access</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Secret</TableHead>
              <TableHead>Last Updated</TableHead>
              <TableHead className="w-[80px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={7} className="py-6 text-center">
                  <div className="flex items-center justify-center gap-2 text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading credentials...
                  </div>
                </TableCell>
              </TableRow>
            )}
            {!isLoading && filteredCredentials.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8">
                  <div className="text-muted-foreground">
                    No credentials found
                    {searchQuery && (
                      <p className="text-sm">Try adjusting your search query</p>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              filteredCredentials.map((credential) => (
                <TableRow key={credential.id}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      <Key className="h-4 w-4 text-muted-foreground" />

                      {credential.name}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {credential.type ?? "unknown"}
                    </Badge>
                  </TableCell>
                  <TableCell>{getAccessBadge(credential.access)}</TableCell>
                  <TableCell>{getStatusBadge(credential.status)}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <div className="font-mono text-xs bg-muted px-2 py-1 rounded">
                        {credential.secrets
                          ? showSecrets[credential.id]
                            ? Object.values(credential.secrets)[0]
                            : "••••••••••••••••"
                          : "Not available"}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={() => toggleShowSecret(credential.id)}
                        disabled={!credential.secrets}
                      >
                        {showSecrets[credential.id] ? (
                          <EyeOff className="h-3 w-3" />
                        ) : (
                          <Eye className="h-3 w-3" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={() => {
                          if (!credential.secrets) {
                            return;
                          }
                          navigator.clipboard.writeText(
                            Object.values(credential.secrets)[0],
                          );
                        }}
                        disabled={!credential.secrets}
                      >
                        <Copy className="h-3 w-3" />
                      </Button>
                    </div>
                  </TableCell>
                  <TableCell>
                    {new Date(credential.updatedAt).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
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
                          onClick={() =>
                            onDeleteCredential &&
                            onDeleteCredential(credential.id)
                          }
                        >
                          <Trash className="h-4 w-4 mr-2" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
