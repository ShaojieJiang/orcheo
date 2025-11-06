import { WorkflowCanvasLayout } from "@features/workflow/pages/workflow-canvas/components/workflow-canvas-layout";
import { useWorkflowCanvasController } from "@features/workflow/pages/workflow-canvas/hooks/controller/use-workflow-canvas-controller";

import type {
  CanvasEdge,
  CanvasNode,
} from "@features/workflow/pages/workflow-canvas/helpers/types";

interface WorkflowCanvasProps {
  initialNodes?: CanvasNode[];
  initialEdges?: CanvasEdge[];
}

export default function WorkflowCanvas({
  initialNodes = [],
  initialEdges = [],
}: WorkflowCanvasProps) {
  const { layoutProps } = useWorkflowCanvasController(
    initialNodes,
    initialEdges,
  );
  return <WorkflowCanvasLayout {...layoutProps} />;
}
