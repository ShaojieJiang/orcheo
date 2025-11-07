import WorkflowNode from "@features/workflow/components/nodes/workflow-node";
import { getNodeIcon } from "@features/workflow/lib/node-icons";

import type { NodeGalleryItem } from "@/features/workflow/components/panels/workflow-node-gallery-data/types";

export const aiGalleryItems: NodeGalleryItem[] = [
  {
    id: "text-generation",
    category: "ai",
    component: (
      <WorkflowNode
        id="text-generation"
        data={{
          label: "Text Generation",
          description: "Generate text with AI",
          iconKey: "textGeneration",
          icon: getNodeIcon("textGeneration"),
          type: "ai",
        }}
      />
    ),
  },
  {
    id: "chat-completion",
    category: "ai",
    component: (
      <WorkflowNode
        id="chat-completion"
        data={{
          label: "Chat Completion",
          description: "Generate chat responses",
          iconKey: "chatCompletion",
          icon: getNodeIcon("chatCompletion"),
          type: "ai",
        }}
      />
    ),
  },
];
