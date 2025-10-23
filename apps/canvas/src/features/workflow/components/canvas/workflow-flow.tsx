import React from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  OnNodesChange,
  OnEdgesChange,
  OnConnect,
  OnNodeClick,
  OnNodeDoubleClick,
  ConnectionLineType,
  MarkerType,
  ReactFlowInstance,
  BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import WorkflowNodeComponent from "@features/workflow/components/nodes/workflow-node";
import ChatTriggerNode from "@features/workflow/components/nodes/chat-trigger-node";
import StartEndNode from "@features/workflow/components/nodes/start-end-node";
import { cn } from "@/lib/utils";

export interface WorkflowFlowProps<
  NodeType extends Node = Node,
  EdgeType extends Edge = Edge,
> {
  nodes: NodeType[];
  edges: EdgeType[];
  onNodesChange?: OnNodesChange<NodeType>;
  onEdgesChange?: OnEdgesChange<EdgeType>;
  onConnect?: OnConnect;
  onNodeClick?: OnNodeClick;
  onNodeDoubleClick?: OnNodeDoubleClick;
  onInit?: (instance: ReactFlowInstance<NodeType, EdgeType>) => void;
  fitView?: boolean;
  snapToGrid?: boolean;
  snapGrid?: [number, number];
  className?: string;
  children?: React.ReactNode;
  showMiniMap?: boolean;
  showControls?: boolean;
  showBackground?: boolean;
  backgroundVariant?: BackgroundVariant;
  editable?: boolean;
  nodesDraggable?: boolean;
  nodesConnectable?: boolean;
  nodesFocusable?: boolean;
  elementsSelectable?: boolean;
  zoomOnDoubleClick?: boolean;
}

const nodeTypes = {
  default: WorkflowNodeComponent,
  chatTrigger: ChatTriggerNode,
  startEnd: StartEndNode,
};

const defaultEdgeOptions = {
  style: { stroke: "#99a1b3", strokeWidth: 2 },
  type: "smoothstep" as const,
  markerEnd: {
    type: MarkerType.ArrowClosed,
  },
};

const getMiniMapNodeColor = (node: Node) => {
  switch (node.data?.type) {
    case "api":
      return "#93c5fd";
    case "function":
      return "#d8b4fe";
    case "trigger":
      return "#fcd34d";
    case "data":
      return "#86efac";
    case "ai":
      return "#a5b4fc";
    case "chatTrigger":
      return "#fdba74";
    case "python":
      return "#fb923c";
    case "start":
      return "#86efac";
    case "end":
      return "#fca5a5";
    default:
      return "#e2e8f0";
  }
};

/**
 * WorkflowFlow - A reusable ReactFlow wrapper component with consistent styling
 * and configuration for both Editor and Execution pages.
 *
 * This component provides:
 * - Consistent node types (default, chatTrigger, startEnd)
 * - Consistent edge styling
 * - Optional MiniMap, Controls, and Background
 * - Configurable interaction modes (editable vs read-only)
 */
export default function WorkflowFlow<
  NodeType extends Node = Node,
  EdgeType extends Edge = Edge,
>({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onNodeClick,
  onNodeDoubleClick,
  onInit,
  fitView = true,
  snapToGrid = false,
  snapGrid = [15, 15],
  className,
  children,
  showMiniMap = true,
  showControls = true,
  showBackground = true,
  backgroundVariant = BackgroundVariant.Dots,
  editable = true,
  nodesDraggable,
  nodesConnectable,
  nodesFocusable,
  elementsSelectable,
  zoomOnDoubleClick = true,
}: WorkflowFlowProps<NodeType, EdgeType>) {
  // Default interaction props based on editable mode
  const defaultNodesDraggable = nodesDraggable ?? editable;
  const defaultNodesConnectable = nodesConnectable ?? editable;
  const defaultNodesFocusable = nodesFocusable ?? true;
  const defaultElementsSelectable = elementsSelectable ?? editable;

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      onNodeClick={onNodeClick}
      onNodeDoubleClick={onNodeDoubleClick}
      onInit={onInit}
      nodeTypes={nodeTypes}
      fitView={fitView}
      snapToGrid={snapToGrid}
      snapGrid={snapGrid}
      defaultEdgeOptions={defaultEdgeOptions}
      connectionLineType={ConnectionLineType.SmoothStep}
      connectionLineStyle={{ stroke: "#99a1b3", strokeWidth: 2 }}
      proOptions={{ hideAttribution: true }}
      nodesDraggable={defaultNodesDraggable}
      nodesConnectable={defaultNodesConnectable}
      nodesFocusable={defaultNodesFocusable}
      elementsSelectable={defaultElementsSelectable}
      zoomOnDoubleClick={zoomOnDoubleClick}
      className={cn("h-full", className)}
    >
      {showBackground && <Background variant={backgroundVariant} />}

      {showControls && <Controls />}

      {showMiniMap && (
        <MiniMap
          nodeStrokeWidth={3}
          zoomable
          pannable
          nodeColor={getMiniMapNodeColor}
          style={{
            backgroundColor: "hsl(var(--background))",
            border: "1px solid hsl(var(--border))",
          }}
          maskColor="hsl(var(--muted) / 0.6)"
        />
      )}

      {children}
    </ReactFlow>
  );
}
