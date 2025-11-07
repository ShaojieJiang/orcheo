export const NODE_CATEGORIES = {
  all: "All Nodes",
  special: "Special Nodes",
  triggers: "Triggers",
  actions: "Actions",
  logic: "Logic & Flow",
  data: "Data Processing",
  ai: "AI & ML",
} as const;

export type NodeCategory = keyof typeof NODE_CATEGORIES;
