import WorkflowNode from "@features/workflow/components/nodes/workflow-node";
import { getNodeIcon } from "@features/workflow/lib/node-icons";

import type { NodeGalleryItem } from "@/features/workflow/components/panels/workflow-node-gallery-data/types";

export const triggerGalleryItems: NodeGalleryItem[] = [
  {
    id: "webhook-trigger",
    category: "triggers",
    component: (
      <WorkflowNode
        id="webhook-trigger"
        data={{
          label: "Webhook",
          description: "Trigger on HTTP webhook",
          iconKey: "webhook",
          icon: getNodeIcon("webhook"),
          type: "trigger",
        }}
      />
    ),
  },
  {
    id: "manual-trigger",
    category: "triggers",
    component: (
      <WorkflowNode
        id="manual-trigger"
        data={{
          label: "Manual",
          description: "Trigger on-demand from the dashboard",
          iconKey: "manualTrigger",
          icon: getNodeIcon("manualTrigger"),
          type: "trigger",
        }}
      />
    ),
  },
  {
    id: "http-polling-trigger",
    category: "triggers",
    component: (
      <WorkflowNode
        id="http-polling-trigger"
        data={{
          label: "HTTP Polling",
          description: "Poll an API on a schedule",
          iconKey: "httpPolling",
          icon: getNodeIcon("httpPolling"),
          type: "trigger",
        }}
      />
    ),
  },
  {
    id: "schedule-trigger",
    category: "triggers",
    component: (
      <WorkflowNode
        id="schedule-trigger"
        data={{
          label: "Schedule",
          description: "Trigger on schedule",
          iconKey: "schedule",
          icon: getNodeIcon("schedule"),
          type: "trigger",
        }}
      />
    ),
  },
];
