import WorkflowNode from "@features/workflow/components/nodes/workflow-node";
import { getNodeIcon } from "@features/workflow/lib/node-icons";

import type { NodeGalleryItem } from "@/features/workflow/components/panels/workflow-node-gallery-data/types";

export const dataGalleryItems: NodeGalleryItem[] = [
  {
    id: "transform",
    category: "data",
    component: (
      <WorkflowNode
        id="transform"
        data={{
          label: "Transform",
          description: "Transform data",
          iconKey: "transform",
          icon: getNodeIcon("transform"),
          type: "data",
        }}
      />
    ),
  },
  {
    id: "python-code",
    category: "data",
    component: (
      <WorkflowNode
        id="python-code"
        data={{
          label: "Python Code",
          description: "Execute custom Python scripts",
          iconKey: "python",
          icon: getNodeIcon("python"),
          type: "python",
        }}
      />
    ),
  },
  {
    id: "database",
    category: "data",
    component: (
      <WorkflowNode
        id="database"
        data={{
          label: "Database",
          description: "Query database",
          iconKey: "database",
          icon: getNodeIcon("database"),
          type: "data",
        }}
      />
    ),
  },
];
