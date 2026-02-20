import type React from "react";
import type { Connection, Node, ReactFlowInstance } from "@xyflow/react";

import { toast } from "@/hooks/use-toast";
import {
  validateConnection,
  validateNodeCredentials,
  type ValidationError,
} from "@features/workflow/components/canvas/connection-validator";
import { generateRandomId } from "@features/workflow/pages/workflow-canvas/helpers/id";
import type {
  CanvasEdge,
  CanvasNode,
} from "@features/workflow/pages/workflow-canvas/helpers/types";

type Getter<T> = () => T;

type RunValidationDependencies = {
  getNodes: Getter<CanvasNode[]>;
  getEdges: Getter<CanvasEdge[]>;
  setValidationErrors: React.Dispatch<React.SetStateAction<ValidationError[]>>;
  setIsValidating: React.Dispatch<React.SetStateAction<boolean>>;
  setLastValidationRun: React.Dispatch<React.SetStateAction<string | null>>;
};

export const createRunPublishValidation =
  ({
    getNodes,
    getEdges,
    setValidationErrors,
    setIsValidating,
    setLastValidationRun,
  }: RunValidationDependencies) =>
  () => {
    setIsValidating(true);

    window.setTimeout(() => {
      const nodes = getNodes();
      const edges = getEdges();

      const normalizedNodes = nodes.map((node) => ({
        ...node,
        data: {
          ...node.data,
          label:
            typeof node.data.label === "string"
              ? node.data.label
              : ((node.data as { label?: unknown; name?: unknown }).label ??
                (node.data as { name?: unknown }).name ??
                node.id),
          credentials:
            (node.data as { credentials?: { id?: string } | null })
              .credentials ?? null,
        },
      }));

      const evaluatedEdges: CanvasEdge[] = [];
      const connectionErrors = edges
        .map((edge) => {
          const error = validateConnection(
            {
              source: edge.source,
              target: edge.target,
              sourceHandle: edge.sourceHandle ?? null,
              targetHandle: edge.targetHandle ?? null,
            } as Connection,
            normalizedNodes as unknown as Node<{
              type?: string;
              label?: string;
              credentials?: { id?: string } | null;
            }>[],
            evaluatedEdges,
          );

          evaluatedEdges.push(edge);

          return error;
        })
        .filter((error): error is ValidationError => Boolean(error));

      const credentialErrors = normalizedNodes
        .map((node) =>
          validateNodeCredentials(
            node as unknown as Node<{
              type?: string;
              label?: string;
              credentials?: { id?: string } | null;
            }>,
          ),
        )
        .filter((error): error is ValidationError => Boolean(error));

      const readinessErrors = [...connectionErrors, ...credentialErrors];

      if (nodes.length === 0) {
        readinessErrors.push({
          id: generateRandomId("validation"),
          type: "node",
          message: "Add at least one node before publishing the workflow.",
        });
      }

      setValidationErrors(readinessErrors);
      setIsValidating(false);
      const completedAt = new Date().toISOString();
      setLastValidationRun(completedAt);

      toast({
        title:
          readinessErrors.length === 0
            ? "Workflow passed all validation checks"
            : `Validation found ${readinessErrors.length} issue${
                readinessErrors.length === 1 ? "" : "s"
              }`,
        description:
          readinessErrors.length === 0
            ? "You can proceed to publish once final reviews are complete."
            : "Resolve the flagged items from the Readiness tab or directly on the canvas.",
      });
    }, 250);
  };

type DismissValidationDependencies = {
  setValidationErrors: React.Dispatch<React.SetStateAction<ValidationError[]>>;
};

export const createHandleDismissValidation =
  ({ setValidationErrors }: DismissValidationDependencies) =>
  (id: string) => {
    setValidationErrors((prev) => prev.filter((error) => error.id !== id));
  };

type FixValidationDependencies = {
  getNodes: Getter<CanvasNode[]>;
  setActiveTab: React.Dispatch<React.SetStateAction<string>>;
  setSelectedNodeId: React.Dispatch<React.SetStateAction<string | null>>;
  reactFlowInstance: React.MutableRefObject<ReactFlowInstance<
    CanvasNode,
    CanvasEdge
  > | null>;
};

export const createHandleFixValidation =
  ({
    getNodes,
    setActiveTab,
    setSelectedNodeId,
    reactFlowInstance,
  }: FixValidationDependencies) =>
  (error: ValidationError) => {
    setActiveTab("workflow");
    const nodes = getNodes();

    if (error.nodeId) {
      const nodeToFocus = nodes.find((node) => node.id === error.nodeId);
      if (nodeToFocus) {
        setSelectedNodeId(nodeToFocus.id);
        requestAnimationFrame(() => {
          reactFlowInstance.current?.setCenter(
            nodeToFocus.position.x + (nodeToFocus.width ?? 0) / 2,
            nodeToFocus.position.y + (nodeToFocus.height ?? 0) / 2,
            { zoom: 1.15, duration: 400 },
          );
        });
      }
      return;
    }

    if (error.sourceId && error.targetId) {
      toast({
        title: "Review the highlighted connection",
        description: `${error.sourceId} → ${error.targetId} needs to be updated before publishing.`,
      });
    }
  };
