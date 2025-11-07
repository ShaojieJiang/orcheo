import React from "react";
import { BarChart } from "lucide-react";

import { buildSidebarNode, type NodeCategory } from "../sidebar-panel.types";

export const visualizationCategory: NodeCategory = {
  id: "visualization",
  name: "Visualization",
  icon: <BarChart className="h-4 w-4 text-orange-500" />,
  nodes: [
    buildSidebarNode({
      id: "bar-chart",
      name: "Bar Chart",
      description: "Create bar charts from data",
      iconKey: "barChart",
      type: "visualization",
    }),
    buildSidebarNode({
      id: "line-chart",
      name: "Line Chart",
      description: "Create line charts from data",
      iconKey: "lineChart",
      type: "visualization",
    }),
    buildSidebarNode({
      id: "pie-chart",
      name: "Pie Chart",
      description: "Create pie charts from data",
      iconKey: "pieChart",
      type: "visualization",
    }),
  ],
};
