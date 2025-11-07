import React from "react";
import { Globe } from "lucide-react";

import { buildSidebarNode, type NodeCategory } from "../sidebar-panel.types";

export const actionCategory: NodeCategory = {
  id: "actions",
  name: "Actions",
  icon: <Globe className="h-4 w-4 text-blue-500" />,
  nodes: [
    buildSidebarNode({
      id: "http-request",
      name: "HTTP Request",
      description: "Make HTTP requests to external APIs",
      iconKey: "http",
      type: "api",
    }),
    buildSidebarNode({
      id: "email-send",
      name: "Send Email",
      description: "Send and receive emails",
      iconKey: "email",
      type: "api",
    }),
    buildSidebarNode({
      id: "slack",
      name: "Slack",
      description: "Interact with Slack channels",
      iconKey: "slack",
      type: "api",
      backendType: "SlackNode",
    }),
  ],
};
