import React from "react";
import { Database } from "lucide-react";

import { DEFAULT_PYTHON_CODE } from "@features/workflow/lib/python-node";

import { buildSidebarNode, type NodeCategory } from "../sidebar-panel.types";

export const dataCategory: NodeCategory = {
  id: "data",
  name: "Data Processing",
  icon: <Database className="h-4 w-4 text-green-500" />,
  nodes: [
    buildSidebarNode({
      id: "database",
      name: "Database",
      description: "Query databases with SQL",
      iconKey: "database",
      type: "data",
    }),
    buildSidebarNode({
      id: "transform",
      name: "Transform",
      description: "Transform data between steps",
      iconKey: "transform",
      type: "data",
    }),
    buildSidebarNode({
      id: "python-code",
      name: "Python Code",
      description: "Execute custom Python scripts",
      iconKey: "python",
      type: "python",
      data: {
        code: DEFAULT_PYTHON_CODE,
        backendType: "PythonCode",
      },
    }),
    buildSidebarNode({
      id: "filter",
      name: "Filter Data",
      description: "Filter data based on conditions",
      iconKey: "filterData",
      type: "data",
    }),
    buildSidebarNode({
      id: "aggregate",
      name: "Aggregate",
      description: "Group and aggregate data",
      iconKey: "aggregate",
      type: "data",
    }),
  ],
};
