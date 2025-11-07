import { NODE_CATEGORIES } from "@/features/workflow/components/panels/workflow-node-gallery-data/categories";
import { actionGalleryItems } from "@/features/workflow/components/panels/workflow-node-gallery-data/items/actions";
import { aiGalleryItems } from "@/features/workflow/components/panels/workflow-node-gallery-data/items/ai";
import { dataGalleryItems } from "@/features/workflow/components/panels/workflow-node-gallery-data/items/data";
import { logicGalleryItems } from "@/features/workflow/components/panels/workflow-node-gallery-data/items/logic";
import { specialGalleryItems } from "@/features/workflow/components/panels/workflow-node-gallery-data/items/special";
import { triggerGalleryItems } from "@/features/workflow/components/panels/workflow-node-gallery-data/items/triggers";
import type { NodeCategory } from "@/features/workflow/components/panels/workflow-node-gallery-data/categories";
import type { NodeGalleryItem } from "@/features/workflow/components/panels/workflow-node-gallery-data/types";

export { NODE_CATEGORIES };
export type { NodeCategory, NodeGalleryItem };

export const NODE_GALLERY_ITEMS: NodeGalleryItem[] = [
  ...specialGalleryItems,
  ...triggerGalleryItems,
  ...actionGalleryItems,
  ...logicGalleryItems,
  ...dataGalleryItems,
  ...aiGalleryItems,
];
