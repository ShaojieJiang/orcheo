import WorkflowNode from "@features/workflow/components/nodes/workflow-node";
import { getNodeIcon } from "@features/workflow/lib/node-icons";

import type { NodeGalleryItem } from "@/features/workflow/components/panels/workflow-node-gallery-data/types";

export const actionGalleryItems: NodeGalleryItem[] = [
  {
    id: "http-request",
    category: "actions",
    component: (
      <WorkflowNode
        id="http-request"
        data={{
          label: "HTTP Request",
          description: "Make HTTP requests",
          iconKey: "http",
          icon: getNodeIcon("http"),
          type: "api",
        }}
      />
    ),
  },
  {
    id: "email-send",
    category: "actions",
    component: (
      <WorkflowNode
        id="email-send"
        data={{
          label: "Send Email",
          description: "Send an email",
          iconKey: "email",
          icon: getNodeIcon("email"),
          type: "api",
        }}
      />
    ),
  },
];
