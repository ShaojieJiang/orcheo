import React from "react";

import type { NodeCategory } from "@/features/workflow/components/panels/workflow-node-gallery-data/categories";

export interface NodeGalleryItem {
  id: string;
  category: NodeCategory;
  component: React.ReactNode;
}
