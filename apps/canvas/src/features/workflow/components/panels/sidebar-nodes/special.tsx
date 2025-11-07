import React from "react";
import { Settings } from "lucide-react";

import { buildSidebarNode, type NodeCategory } from "../sidebar-panel.types";

export const specialCategory: NodeCategory = {
  id: "special",
  name: "Special Nodes",
  icon: <Settings className="h-4 w-4 text-gray-500" />,
  nodes: [
    buildSidebarNode({
      id: "start-node",
      name: "Workflow Start",
      description: "Beginning of the workflow",
      iconKey: "start",
      type: "start",
    }),
    buildSidebarNode({
      id: "end-node",
      name: "Workflow End",
      description: "End of the workflow",
      iconKey: "end",
      type: "end",
    }),
    buildSidebarNode({
      id: "group-node",
      name: "Node Group",
      description: "Group related nodes together",
      iconKey: "group",
      type: "group",
    }),
    buildSidebarNode({
      id: "sticky-note",
      name: "Sticky Note",
      description: "Add workflow annotations",
      iconKey: "stickyNote",
      type: "annotation",
      data: {
        color: "yellow",
        content: "Document why this branch exists.",
      },
    }),
  ],
};
