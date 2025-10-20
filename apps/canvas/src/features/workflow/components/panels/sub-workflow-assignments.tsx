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

interface AssignedNode {
  id: string;
  data?: {
    label?: string;
    type?: string;
    subWorkflowId?: string | null;
    subWorkflowName?: string;
  };
}

interface SubWorkflowTemplateSummary {
  id: string;
  name: string;
  description?: string;
}

interface SubWorkflowAssignmentsProps {
  nodes: AssignedNode[];
  subWorkflows: SubWorkflowTemplateSummary[];
  onAssign: (nodeId: string, subWorkflowId: string | null) => void;
  className?: string;
}

export default function SubWorkflowAssignments({
  nodes,
  subWorkflows,
  onAssign,
  className,
}: SubWorkflowAssignmentsProps) {
  const eligibleNodes = useMemo(() => {
    return nodes
      .filter((node) => {
        const nodeType = node.data?.type ?? "default";
        return nodeType === "subWorkflow" || Boolean(node.data?.subWorkflowId);
      })
      .map((node) => ({
        id: node.id,
        label: node.data?.label ?? node.id,
        subWorkflowId: node.data?.subWorkflowId ?? null,
        type: node.data?.type ?? "default",
      }));
  }, [nodes]);

  const sortedTemplates = useMemo(() => {
    return [...subWorkflows].sort((a, b) => a.name.localeCompare(b.name));
  }, [subWorkflows]);

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Node Sub-Workflow Mapping</CardTitle>
        <CardDescription>
          Attach reusable sub-workflows to canvas nodes to keep orchestrations
          consistent.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {eligibleNodes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No nodes are currently configured for sub-workflows. Insert a
            reusable flow to get started.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-1/3">Node</TableHead>
                <TableHead className="w-1/3">Type</TableHead>
                <TableHead className="w-1/3 text-right">
                  Linked Sub-Workflow
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
                      value={node.subWorkflowId ?? "unassigned"}
                      onValueChange={(value) =>
                        onAssign(node.id, value === "unassigned" ? null : value)
                      }
                    >
                      <SelectTrigger className="w-full justify-end">
                        <SelectValue placeholder="Select sub-workflow" />
                      </SelectTrigger>
                      <SelectContent align="end">
                        <SelectItem value="unassigned">Unassigned</SelectItem>
                        {sortedTemplates.map((template) => (
                          <SelectItem key={template.id} value={template.id}>
                            {template.name}
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
