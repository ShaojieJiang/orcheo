import React, { useState, useEffect } from "react";
import type { Connection, Edge, Node } from "@xyflow/react";
import { AlertCircle, X } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/design-system/ui/alert";
import { Button } from "@/design-system/ui/button";
import { cn } from "@/lib/utils";

export interface ValidationError {
  id: string;
  type: "connection" | "credential" | "node";
  message: string;
  sourceId?: string;
  targetId?: string;
  nodeName?: string;
  nodeId?: string;
}

interface ConnectionValidatorProps {
  errors: ValidationError[];
  onDismiss: (id: string) => void;
  onFix?: (error: ValidationError) => void;
  className?: string;
}

interface ValidatorNodeData {
  type?: string;
  label?: string;
  credentials?: {
    id?: string;
  } | null;
}

type ValidatorNode = Node<ValidatorNodeData>;
type ValidatorEdge = Edge<Record<string, unknown>>;

export default function ConnectionValidator({
  errors,
  onDismiss,
  onFix,
  className,
}: ConnectionValidatorProps) {
  const [visibleErrors, setVisibleErrors] = useState<ValidationError[]>([]);

  useEffect(() => {
    setVisibleErrors(errors);
  }, [errors]);

  const handleDismiss = (id: string) => {
    setVisibleErrors((prev) => prev.filter((error) => error.id !== id));
    onDismiss(id);
  };

  if (visibleErrors.length === 0) return null;

  return (
    <div
      className={cn(
        "absolute bottom-4 right-4 z-10 w-96 max-h-[calc(100vh-8rem)] overflow-y-auto space-y-2",
        className,
      )}
    >
      {visibleErrors.map((error) => (
        <Alert
          key={error.id}
          variant="destructive"
          className="flex items-start pr-12 relative"
        >
          <AlertCircle className="h-4 w-4 mt-0.5" />

          <div className="ml-2 flex-1">
            <AlertTitle>
              {error.type === "connection"
                ? "Invalid Connection"
                : error.type === "credential"
                  ? "Missing Credentials"
                  : "Node Configuration Error"}
            </AlertTitle>
            <AlertDescription className="text-sm mt-1">
              {error.message}
              {error.type === "connection" &&
                error.sourceId &&
                error.targetId && (
                  <div className="mt-1 text-xs">
                    <span className="font-medium">From:</span> {error.sourceId}
                    <br />
                    <span className="font-medium">To:</span> {error.targetId}
                  </div>
                )}
              {error.type === "node" && error.nodeName && (
                <div className="mt-1 text-xs">
                  <span className="font-medium">Node:</span> {error.nodeName}
                </div>
              )}
              {onFix && (
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-2 bg-destructive/10 border-destructive/20 hover:bg-destructive/20"
                  onClick={() => onFix(error)}
                >
                  Fix Issue
                </Button>
              )}
            </AlertDescription>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 absolute top-2 right-2 text-destructive-foreground/70 hover:text-destructive-foreground"
            onClick={() => handleDismiss(error.id)}
          >
            <X className="h-3 w-3" />
          </Button>
        </Alert>
      ))}
    </div>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function validateConnection(
  connection: Connection,
  nodes: ValidatorNode[],
  edges: ValidatorEdge[],
): ValidationError | null {
  // Get source and target nodes
  const sourceNode = nodes.find((node) => node.id === connection.source);
  const targetNode = nodes.find((node) => node.id === connection.target);

  if (!sourceNode || !targetNode) {
    return {
      id: `conn-${Date.now()}`,
      type: "connection",
      message: "Source or target node not found",
      sourceId: connection.source,
      targetId: connection.target,
    };
  }

  // Check if connection already exists
  const connectionExists = edges.some(
    (edge) =>
      edge.source === connection.source && edge.target === connection.target,
  );

  if (connectionExists) {
    return {
      id: `conn-${Date.now()}`,
      type: "connection",
      message: "Connection already exists between these nodes",
      sourceId: connection.source,
      targetId: connection.target,
    };
  }

  // Check for incompatible node types (example validation)
  if (
    sourceNode.data.type === "trigger" &&
    targetNode.data.type === "trigger"
  ) {
    return {
      id: `conn-${Date.now()}`,
      type: "connection",
      message: "Cannot connect a trigger node to another trigger node",
      sourceId: connection.source,
      targetId: connection.target,
    };
  }

  // Check for circular references
  const wouldCreateCycle = checkForCycle(
    connection.source,
    connection.target,
    edges,
  );
  if (wouldCreateCycle) {
    return {
      id: `conn-${Date.now()}`,
      type: "connection",
      message: "This connection would create a circular reference",
      sourceId: connection.source,
      targetId: connection.target,
    };
  }

  return null;
}

// eslint-disable-next-line react-refresh/only-export-components
export function validateNodeCredentials(
  node: ValidatorNode,
): ValidationError | null {
  // Example validation for credentials
  if (
    (node.data.type === "api" ||
      node.data.type === "database" ||
      node.data.type === "ai") &&
    (!node.data.credentials || !node.data.credentials.id)
  ) {
    return {
      id: `cred-${node.id}`,
      type: "credential",
      message: `${node.data.label} requires credentials to be configured`,
      nodeName: node.data.label,
      nodeId: node.id,
    };
  }

  return null;
}

// Helper function to check for cycles in the graph
function checkForCycle(
  source: string,
  target: string,
  edges: ValidatorEdge[],
  visited: Set<string> = new Set(),
): boolean {
  if (source === target) return true;
  if (visited.has(target)) return false;

  visited.add(target);

  const outgoingEdges = edges.filter((edge) => edge.source === target);
  for (const edge of outgoingEdges) {
    if (checkForCycle(source, edge.target, edges, visited)) {
      return true;
    }
  }

  return false;
}
