import type React from "react";
import type { ReactFlowInstance } from "@xyflow/react";

import { toast } from "@/hooks/use-toast";
import {
  DEFAULT_NODE_LABEL,
  createIdentityAllocator,
} from "@features/workflow/pages/workflow-canvas/helpers/node-identity";
import type {
  WorkflowEdge as PersistedWorkflowEdge,
  WorkflowNode as PersistedWorkflowNode,
} from "@features/workflow/data/workflow-data";
import {
  SUBWORKFLOW_LIBRARY,
  type SubworkflowTemplate,
} from "@features/workflow/pages/workflow-canvas/helpers/subworkflow-library";
import { generateRandomId } from "@features/workflow/pages/workflow-canvas/helpers/id";
import type {
  CanvasEdge,
  CanvasNode,
} from "@features/workflow/pages/workflow-canvas/helpers/types";

type Getter<T> = () => T;

type CreateSubworkflowHandlerArgs = {
  getSelectedNodes: Getter<CanvasNode[]>;
  setSubworkflows: React.Dispatch<React.SetStateAction<SubworkflowTemplate[]>>;
};

export const createHandleCreateSubworkflow =
  ({ getSelectedNodes, setSubworkflows }: CreateSubworkflowHandlerArgs) =>
  () => {
    const selectedNodes = getSelectedNodes();
    const timestamp = new Date().toISOString();
    const inferredTags = Array.from(
      new Set(
        selectedNodes
          .map((node) =>
            typeof node.data.type === "string" ? node.data.type : "workflow",
          )
          .filter(Boolean),
      ),
    ).slice(0, 4);

    const template: SubworkflowTemplate = {
      id: generateRandomId("subflow"),
      name:
        selectedNodes.length > 0
          ? `${selectedNodes.length}-step sub-workflow`
          : "Draft sub-workflow",
      description:
        selectedNodes.length > 0
          ? "Captured the selected nodes so the pattern can be reused across projects."
          : "Start from an empty template and drag nodes into the canvas to define the steps.",
      tags: inferredTags.length > 0 ? inferredTags : ["workflow"],
      version: "0.1.0",
      status: "beta",
      usageCount: 0,
      lastUpdated: timestamp,
    };

    setSubworkflows((prev) => [template, ...prev]);
    toast({
      title: "Sub-workflow draft created",
      description:
        "Find it in the Readiness tab to document, version, and share with your team.",
    });
  };

type DeleteSubworkflowHandlerArgs = {
  setSubworkflows: React.Dispatch<React.SetStateAction<SubworkflowTemplate[]>>;
};

export const createHandleDeleteSubworkflow =
  ({ setSubworkflows }: DeleteSubworkflowHandlerArgs) =>
  (id: string) => {
    setSubworkflows((prev) =>
      prev.filter((subworkflow) => subworkflow.id !== id),
    );
    toast({
      title: "Sub-workflow removed",
      description:
        "It will remain available in version history for audit purposes.",
    });
  };

type InsertSubworkflowHandlerArgs = {
  nodesRef: React.MutableRefObject<CanvasNode[]>;
  setNodes: React.Dispatch<React.SetStateAction<CanvasNode[]>>;
  setEdges: React.Dispatch<React.SetStateAction<CanvasEdge[]>>;
  setSubworkflows: React.Dispatch<React.SetStateAction<SubworkflowTemplate[]>>;
  convertPersistedNodesToCanvas: (
    nodes: PersistedWorkflowNode[],
  ) => CanvasNode[];
  convertPersistedEdgesToCanvas: (
    edges: PersistedWorkflowEdge[],
  ) => CanvasEdge[];
  setSelectedNodeId: React.Dispatch<React.SetStateAction<string | null>>;
  setActiveTab: React.Dispatch<React.SetStateAction<string>>;
  reactFlowInstance: React.MutableRefObject<ReactFlowInstance<
    CanvasNode,
    CanvasEdge
  > | null>;
};

export const createHandleInsertSubworkflow =
  ({
    nodesRef,
    setNodes,
    setEdges,
    setSubworkflows,
    convertPersistedNodesToCanvas,
    convertPersistedEdgesToCanvas,
    setSelectedNodeId,
    setActiveTab,
    reactFlowInstance,
  }: InsertSubworkflowHandlerArgs) =>
  (subworkflow: SubworkflowTemplate) => {
    const libraryEntry = SUBWORKFLOW_LIBRARY[subworkflow.id];

    if (!libraryEntry) {
      toast({
        title: "Template unavailable",
        description:
          "This sub-workflow doesn't have a canvas definition yet. Please try another template.",
        variant: "destructive",
      });
      return;
    }

    const templateXs = libraryEntry.nodes.map((node) => node.position?.x ?? 0);
    const templateYs = libraryEntry.nodes.map((node) => node.position?.y ?? 0);
    const templateMinX = templateXs.length > 0 ? Math.min(...templateXs) : 0;
    const templateMinY = templateYs.length > 0 ? Math.min(...templateYs) : 0;

    const existingNodes = nodesRef.current;
    const existingMaxX = existingNodes.length
      ? Math.max(...existingNodes.map((node) => node.position?.x ?? 0))
      : 0;
    const existingMinY = existingNodes.length
      ? Math.min(...existingNodes.map((node) => node.position?.y ?? 0))
      : 0;

    const insertionX = existingNodes.length > 0 ? existingMaxX + 320 : 200;
    const insertionY = existingNodes.length > 0 ? existingMinY : 200;

    const idMap = new Map<string, string>();
    const allocateIdentity = createIdentityAllocator(nodesRef.current);

    const remappedNodes = libraryEntry.nodes.map((node) => {
      const baseLabel =
        typeof node.data?.label === "string" && node.data.label.length > 0
          ? node.data.label
          : typeof node.data?.type === "string" && node.data.type.length > 0
            ? `${node.data.type} Node`
            : DEFAULT_NODE_LABEL;
      const { id: newId, label } = allocateIdentity(baseLabel);
      idMap.set(node.id, newId);

      return {
        ...node,
        id: newId,
        position: {
          x: insertionX + ((node.position?.x ?? 0) - templateMinX),
          y: insertionY + ((node.position?.y ?? 0) - templateMinY),
        },
        data: {
          ...node.data,
          type: node.data?.type ?? node.type ?? "default",
          status: "idle",
          label,
        },
      } as PersistedWorkflowNode;
    });

    const remappedEdges = libraryEntry.edges.map((edge) => ({
      ...edge,
      id: generateRandomId("edge"),
      source: idMap.get(edge.source) ?? edge.source,
      target: idMap.get(edge.target) ?? edge.target,
    }));

    const canvasNodes = convertPersistedNodesToCanvas(remappedNodes);
    const canvasEdges = convertPersistedEdgesToCanvas(remappedEdges);

    setNodes((current) => [...current, ...canvasNodes]);
    setEdges((current) => [...current, ...canvasEdges]);

    setSubworkflows((prev) =>
      prev.map((template) =>
        template.id === subworkflow.id
          ? {
              ...template,
              usageCount: template.usageCount + 1,
              lastUpdated: new Date().toISOString(),
            }
          : template,
      ),
    );

    if (canvasNodes.length > 0) {
      setSelectedNodeId(canvasNodes[0].id);
      setActiveTab("workflow");

      const instance = reactFlowInstance.current;
      if (instance) {
        const insertedXs = canvasNodes.map((node) => node.position.x);
        const insertedYs = canvasNodes.map((node) => node.position.y);
        const minX = Math.min(...insertedXs);
        const maxX = Math.max(...insertedXs);
        const minY = Math.min(...insertedYs);
        const maxY = Math.max(...insertedYs);
        const centerX = minX + (maxX - minX) / 2;
        const centerY = minY + (maxY - minY) / 2;

        instance.setCenter(centerX, centerY, {
          zoom: 1.15,
          duration: 400,
        });
      }
    }

    toast({
      title: `${subworkflow.name} inserted`,
      description: `Added ${canvasNodes.length} nodes and ${canvasEdges.length} connections to the canvas.`,
    });
  };
