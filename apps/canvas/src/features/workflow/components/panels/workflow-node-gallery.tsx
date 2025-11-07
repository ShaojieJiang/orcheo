import React, { useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { Tabs, TabsList, TabsTrigger } from "@/design-system/ui/tabs";
import { Input } from "@/design-system/ui/input";
import { ScrollArea } from "@/design-system/ui/scroll-area";
import { Search } from "lucide-react";
import {
  NODE_CATEGORIES,
  NODE_GALLERY_ITEMS,
  type NodeCategory,
} from "./workflow-node-gallery-data";

export default function WorkflowNodeGallery() {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState<NodeCategory>("all");

  // Filter nodes based on search query and active category
  const filteredNodes = useMemo(() => {
    return NODE_GALLERY_ITEMS.filter((node) => {
      const matchesSearch =
        searchQuery === "" ||
        node.id.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesCategory =
        activeCategory === "all" || node.category === activeCategory;

      return matchesSearch && matchesCategory;
    });
  }, [activeCategory, searchQuery]);

  return (
    <div className="flex flex-col h-full border border-border rounded-lg overflow-hidden">
      <div className="p-4 border-b border-border">
        <h3 className="font-medium mb-2">Workflow Nodes</h3>
        <div className="relative">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />

          <Input
            placeholder="Search nodes..."
            className="pl-8"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      <Tabs
        defaultValue="all"
        value={activeCategory}
        onValueChange={setActiveCategory}
        className="flex-1 flex flex-col"
      >
        <div className="border-b border-border overflow-x-auto">
          <TabsList className="h-10 w-full justify-start rounded-none bg-transparent p-0">
            {Object.entries(NODE_CATEGORIES).map(([key, label]) => (
              <TabsTrigger
                key={key}
                value={key}
                className={cn(
                  "h-10 rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none",
                )}
              >
                {label}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>

        <ScrollArea className="flex-1 p-4">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
            {filteredNodes.map((node) => (
              <div key={node.id} className="flex items-center justify-center">
                {node.component}
              </div>
            ))}
            {filteredNodes.length === 0 && (
              <div className="col-span-full flex items-center justify-center h-40 text-muted-foreground">
                No nodes match your search
              </div>
            )}
          </div>
        </ScrollArea>
      </Tabs>
    </div>
  );
}
