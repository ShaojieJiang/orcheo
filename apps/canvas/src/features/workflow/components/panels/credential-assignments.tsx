import React, { useMemo } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
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

interface CredentialSummary {
  id: string;
  name: string;
  type: string;
  access: "private" | "shared" | "public";
}

interface AssignableNode {
  id: string;
  data?: {
    label?: string;
    type?: string;
    credentials?: { id?: string | null } | null;
  };
}

interface CredentialAssignmentsProps {
  nodes: AssignableNode[];
  credentials: CredentialSummary[];
  onAssign: (nodeId: string, credentialId: string | null) => void;
  className?: string;
}

const credentialNodeTypes = new Set(["api", "database", "ai"]);

const accessBadgeVariant: Record<CredentialSummary["access"], string> = {
  private: "bg-blue-100 text-blue-800 border-blue-200",
  shared: "bg-purple-100 text-purple-800 border-purple-200",
  public: "bg-green-100 text-green-800 border-green-200",
};

export default function CredentialAssignments({
  nodes,
  credentials,
  onAssign,
  className,
}: CredentialAssignmentsProps) {
  const eligibleNodes = useMemo(() => {
    return nodes
      .filter((node) => {
        const nodeType = node.data?.type ?? "default";
        return credentialNodeTypes.has(nodeType);
      })
      .map((node) => ({
        id: node.id,
        label: node.data?.label ?? node.id,
        type: node.data?.type ?? "default",
        credentialId: node.data?.credentials?.id ?? null,
      }));
  }, [nodes]);

  const sortedCredentials = useMemo(() => {
    return [...credentials].sort((a, b) => a.name.localeCompare(b.name));
  }, [credentials]);

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Credential Assignments</CardTitle>
        <CardDescription>
          Map vault credentials to workflow nodes that require authenticated
          access.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {eligibleNodes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No nodes currently require credentials. Add an API, database, or AI
            node to configure assignments.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-1/3">Node</TableHead>
                <TableHead className="w-1/3">Type</TableHead>
                <TableHead className="w-1/3 text-right">
                  Assigned Credential
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {eligibleNodes.map((node) => (
                <TableRow key={node.id}>
                  <TableCell>{node.label}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="capitalize">
                      {node.type}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <Select
                      value={node.credentialId ?? "unassigned"}
                      onValueChange={(value) =>
                        onAssign(node.id, value === "unassigned" ? null : value)
                      }
                    >
                      <SelectTrigger className="w-full justify-end">
                        <SelectValue placeholder="Select credential" />
                      </SelectTrigger>
                      <SelectContent align="end">
                        <SelectItem value="unassigned">Unassigned</SelectItem>
                        {sortedCredentials.map((credential) => (
                          <SelectItem key={credential.id} value={credential.id}>
                            <div className="flex items-center justify-between gap-3">
                              <span className="font-medium">
                                {credential.name}
                              </span>
                              <Badge
                                variant="outline"
                                className={
                                  accessBadgeVariant[credential.access]
                                }
                              >
                                {credential.access}
                              </Badge>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
