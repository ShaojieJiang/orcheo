import WorkflowNode from "@features/workflow/components/nodes/workflow-node";
import { getNodeIcon } from "@features/workflow/lib/node-icons";

import type { NodeGalleryItem } from "@/features/workflow/components/panels/workflow-node-gallery-data/types";

export const logicGalleryItems: NodeGalleryItem[] = [
  {
    id: "condition",
    category: "logic",
    component: (
      <WorkflowNode
        id="condition"
        data={{
          label: "If / Else",
          description: "Branch based on a comparison",
          iconKey: "condition",
          icon: getNodeIcon("condition"),
          type: "function",
        }}
      />
    ),
  },
  {
    id: "loop",
    category: "logic",
    component: (
      <WorkflowNode
        id="loop"
        data={{
          label: "While Loop",
          description: "Iterate while a condition is true",
          iconKey: "loop",
          icon: getNodeIcon("loop"),
          type: "function",
        }}
      />
    ),
  },
];
