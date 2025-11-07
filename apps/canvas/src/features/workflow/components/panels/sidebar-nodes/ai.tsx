import React from "react";
import { Sparkles } from "lucide-react";

import { buildSidebarNode, type NodeCategory } from "../sidebar-panel.types";

export const aiCategory: NodeCategory = {
  id: "ai",
  name: "AI & ML",
  icon: <Sparkles className="h-4 w-4 text-indigo-500" />,
  nodes: [
    buildSidebarNode({
      id: "text-generation",
      name: "Text Generation",
      description: "Generate text with AI models",
      iconKey: "textGeneration",
      type: "ai",
    }),
    buildSidebarNode({
      id: "chat-completion",
      name: "Chat Completion",
      description: "Generate chat responses",
      iconKey: "chatCompletion",
      type: "ai",
    }),
    buildSidebarNode({
      id: "classification",
      name: "Classification",
      description: "Classify content with ML models",
      iconKey: "classification",
      type: "ai",
    }),
    buildSidebarNode({
      id: "image-generation",
      name: "Image Generation",
      description: "Generate images with AI",
      iconKey: "imageGeneration",
      type: "ai",
    }),
  ],
};
