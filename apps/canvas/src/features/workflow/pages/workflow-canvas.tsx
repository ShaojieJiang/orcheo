import { useEffect } from "react";
import { WorkflowCanvasLayout } from "@features/workflow/pages/workflow-canvas/components/workflow-canvas-layout";
import { useWorkflowCanvasController } from "@features/workflow/pages/workflow-canvas/hooks/controller/use-workflow-canvas-controller";
import { usePageContext } from "@/hooks/use-page-context";

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

  const { setPageContext } = usePageContext();
  const workflowId = layoutProps.workflowProps.workflowId ?? null;
  const workflowName =
    layoutProps.topNavigationProps.currentWorkflow.name ?? null;

  useEffect(() => {
    setPageContext({
      page: "canvas",
      workflowId,
      workflowName,
    });
  }, [setPageContext, workflowId, workflowName]);

  return <WorkflowCanvasLayout {...layoutProps} />;
}
