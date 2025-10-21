import React, { useMemo } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/design-system/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import { Badge } from "@/design-system/ui/badge";
import { cn } from "@/lib/utils";

interface CredentialSummary {
  id: string;
  name: string;
  type: string;
  access: "private" | "shared" | "public";
}

interface NodeCredentialState {
  id: string;
  label: string;
  type?: string;
  credentialId?: string | null;
  credentialName?: string;
}

interface CredentialAssignmentTableProps {
  nodes: NodeCredentialState[];
  credentials: CredentialSummary[];
  onAssign: (nodeId: string, credentialId: string | null) => void;
  className?: string;
}

const requiresCredential = (type?: string) =>
  type === "api" || type === "database" || type === "ai";

export default function CredentialAssignmentTable({
  nodes,
  credentials,
  onAssign,
  className,
}: CredentialAssignmentTableProps) {
  const nodesNeedingCredentials = useMemo(
    () => nodes.filter((node) => requiresCredential(node.type)),
    [nodes],
  );

  if (nodesNeedingCredentials.length === 0) {
    return (
      <div
        className={cn(
          "rounded-lg border border-dashed border-border bg-muted/20 p-6 text-sm text-muted-foreground",
          className,
        )}
      >
        All nodes are configured with the credentials they require.
      </div>
    );
  }

  return (
    <div className={className}>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[35%]">Node</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Assigned Credential</TableHead>
            <TableHead className="w-[30%]">Select Credential</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {nodesNeedingCredentials.map((node) => {
            const selectedValue = node.credentialId ?? "__none__";

            return (
              <TableRow key={node.id}>
                <TableCell>
                  <div className="flex flex-col">
                    <span className="font-medium">{node.label}</span>
                    <span className="text-xs text-muted-foreground">
                      ID: {node.id}
                    </span>
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className="capitalize">
                    {node.type ?? "unknown"}
                  </Badge>
                </TableCell>
                <TableCell>
                  {node.credentialName ? (
                    <div className="flex flex-col">
                      <span className="font-medium">{node.credentialName}</span>
                      <span className="text-xs text-muted-foreground">
                        {credentials.find(
                          (credential) => credential.id === node.credentialId,
                        )?.type ?? "Custom"}
                      </span>
                    </div>
                  ) : (
                    <span className="text-sm text-muted-foreground">
                      No credential assigned
                    </span>
                  )}
                </TableCell>
                <TableCell>
                  <Select
                    value={selectedValue}
                    onValueChange={(value) =>
                      onAssign(node.id, value === "__none__" ? null : value)
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select credential" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none__">Unassigned</SelectItem>
                      {credentials.map((credential) => (
                        <SelectItem key={credential.id} value={credential.id}>
                          <div className="flex flex-col">
                            <span className="font-medium">
                              {credential.name}
                            </span>
                            <span className="text-xs text-muted-foreground capitalize">
                              {credential.type} · {credential.access}
                            </span>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
