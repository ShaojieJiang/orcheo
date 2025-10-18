import { memo } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  OnEdgesChange,
  OnNodesChange,
  Connection,
} from "reactflow";

import "reactflow/dist/style.css";

type Props = {
  nodes: Node[];
  edges: Edge[];
  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
  onConnect: (connection: Connection) => void;
  onSelectNode: (nodeId: string | null) => void;
};

function CanvasComponent({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onSelectNode,
}: Props) {
  return (
    <div className="canvas">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onSelectionChange={(params) => {
          const selection = params?.nodes?.[0];
          onSelectNode(selection?.id ?? null);
        }}
        fitView
        snapToGrid
        snapGrid={[16, 16]}
      >
        <Background variant="dots" gap={16} size={1} />
        <MiniMap zoomable pannable />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

export const WorkflowCanvas = memo(CanvasComponent);
