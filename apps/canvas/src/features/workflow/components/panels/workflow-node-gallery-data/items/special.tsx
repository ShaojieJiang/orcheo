import GroupNode from "@features/workflow/components/nodes/group-node";
import StartEndNode from "@features/workflow/components/nodes/start-end-node";

import type { NodeGalleryItem } from "@/features/workflow/components/panels/workflow-node-gallery-data/types";

export const specialGalleryItems: NodeGalleryItem[] = [
  {
    id: "start-node",
    category: "special",
    component: (
      <StartEndNode
        id="start-node"
        data={{
          label: "Workflow Start",
          type: "start",
          description: "Beginning of the workflow",
        }}
      />
    ),
  },
  {
    id: "end-node",
    category: "special",
    component: (
      <StartEndNode
        id="end-node"
        data={{
          label: "Workflow End",
          type: "end",
          description: "End of the workflow",
        }}
      />
    ),
  },
  {
    id: "group-node",
    category: "special",
    component: (
      <GroupNode
        id="group-node"
        data={{
          label: "Node Group",
          description: "Group related nodes together",
          nodeCount: 3,
          color: "blue",
        }}
      />
    ),
  },
];
