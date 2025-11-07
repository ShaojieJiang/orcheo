import { useEffect } from "react";
import type { MutableRefObject } from "react";

import type { ReactFlowInstance } from "@xyflow/react";
import type {
  CanvasNode,
  CanvasEdge,
} from "@features/workflow/pages/workflow-canvas/helpers/types";

export function useInitialFitView(
  reactFlowInstance: MutableRefObject<ReactFlowInstance<
    CanvasNode,
    CanvasEdge
  > | null>,
) {
  useEffect(() => {
    const handle = window.setTimeout(() => {
      if (reactFlowInstance.current) {
        reactFlowInstance.current.fitView({ padding: 0.2 });
      }
    }, 100);

    return () => {
      window.clearTimeout(handle);
    };
  }, [reactFlowInstance]);
}
