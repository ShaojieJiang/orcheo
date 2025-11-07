import React from "react";
import { Zap } from "lucide-react";

import { buildSidebarNode, type NodeCategory } from "../sidebar-panel.types";

export const triggerCategory: NodeCategory = {
  id: "triggers",
  name: "Triggers",
  icon: <Zap className="h-4 w-4 text-amber-500" />,
  nodes: [
    buildSidebarNode({
      id: "webhook-trigger",
      name: "Webhook",
      description: "Trigger workflow via HTTP request",
      iconKey: "webhook",
      type: "trigger",
      backendType: "WebhookTriggerNode",
    }),
    buildSidebarNode({
      id: "manual-trigger",
      name: "Manual",
      description: "Dispatch runs from the dashboard",
      iconKey: "manualTrigger",
      type: "trigger",
      backendType: "ManualTriggerNode",
    }),
    buildSidebarNode({
      id: "http-polling-trigger",
      name: "HTTP Polling",
      description: "Poll an API on a schedule",
      iconKey: "httpPolling",
      type: "trigger",
      backendType: "HttpPollingTriggerNode",
    }),
    buildSidebarNode({
      id: "schedule-trigger",
      name: "Schedule",
      description: "Run workflow on a schedule",
      iconKey: "schedule",
      type: "trigger",
      backendType: "CronTriggerNode",
    }),
  ],
};
