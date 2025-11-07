import React, { useMemo, useState } from "react";
import { Input } from "@/design-system/ui/input";
import { Button } from "@/design-system/ui/button";
import { ScrollArea } from "@/design-system/ui/scroll-area";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/design-system/ui/tabs";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/design-system/ui/accordion";
import { Search, ChevronLeft } from "lucide-react";

import { cn } from "@/lib/utils";

import { SidebarNodeItem } from "./sidebar-node-item";
import { favoriteNodes, nodeCategories, recentNodes } from "./sidebar-nodes";
import type { NodeCategory, SidebarNode } from "./sidebar-panel.types";

interface SidebarPanelProps {
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  onAddNode?: (node: SidebarNode) => void;
  className?: string;
  position?: "left" | "canvas";
}

export default function SidebarPanel({
  isCollapsed = false,
  onToggleCollapse,
  onAddNode,
  className,
  position = "left",
}: SidebarPanelProps) {
  const [searchQuery, setSearchQuery] = useState("");

  const filteredCategories = useMemo(
    () => filterCategories(nodeCategories, searchQuery),
    [searchQuery],
  );

  const handleNodeSelect = (node: SidebarNode) => {
    onAddNode?.(node);
  };

  const handleCategoryClick = () => {
    if (isCollapsed) {
      onToggleCollapse?.();
    }
  };

  const containerClasses =
    position === "canvas"
      ? cn(
          "bg-card border border-border rounded-md shadow-md transition-all duration-300",
          isCollapsed ? "w-[50px]" : "w-[300px]",
          className,
        )
      : cn(
          "h-full border-r border-border bg-card transition-all duration-300 flex flex-col",
          isCollapsed ? "w-[50px]" : "w-[300px]",
          className,
        );

  const scrollAreaClass =
    position === "canvas" ? "h-[calc(100vh-280px)]" : "h-[calc(100vh-180px)]";

  return (
    <div className={containerClasses}>
      <div className="flex items-center justify-between p-3 border-b border-border">
        {!isCollapsed && <div className="text-lg font-semibold">Nodes</div>}
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggleCollapse}
          className={cn(isCollapsed && "mx-auto")}
        >
          <ChevronLeft
            className={cn(
              "h-5 w-5 transition-transform",
              isCollapsed && "rotate-180",
            )}
          />
        </Button>
      </div>

      {!isCollapsed && (
        <>
          <div className="p-3">
            <div className="relative">
              <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search nodes..."
                className="pl-8"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
              />
            </div>
          </div>

          <Tabs defaultValue="all" className="flex-1 flex flex-col">
            <div className="px-3">
              <TabsList className="w-full">
                <TabsTrigger value="all" className="flex-1">
                  All
                </TabsTrigger>
                <TabsTrigger value="recent" className="flex-1">
                  Recent
                </TabsTrigger>
                <TabsTrigger value="favorites" className="flex-1">
                  Favorites
                </TabsTrigger>
              </TabsList>
            </div>

            <TabsContent value="all" className="flex-1 mt-0">
              <ScrollArea className={scrollAreaClass}>
                <div className="p-3">
                  {searchQuery && filteredCategories.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      No nodes found matching "{searchQuery}"
                    </div>
                  ) : (
                    <Accordion
                      type="multiple"
                      defaultValue={nodeCategories.map(
                        (category) => category.id,
                      )}
                      className="space-y-2"
                    >
                      {filteredCategories.map((category) => (
                        <AccordionItem
                          key={category.id}
                          value={category.id}
                          className="border-border"
                        >
                          <AccordionTrigger className="py-2 hover:no-underline">
                            <div className="flex items-center gap-2">
                              {category.icon}
                              <span>{category.name}</span>
                            </div>
                          </AccordionTrigger>
                          <AccordionContent>
                            <div className="space-y-1 pl-6">
                              {category.nodes.map((node) => (
                                <SidebarNodeItem
                                  key={node.id}
                                  node={node}
                                  onSelect={handleNodeSelect}
                                />
                              ))}
                            </div>
                          </AccordionContent>
                        </AccordionItem>
                      ))}
                    </Accordion>
                  )}
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="recent" className="flex-1 mt-0">
              <ScrollArea className={scrollAreaClass}>
                <div className="p-3 space-y-2">
                  {recentNodes.map((node) => (
                    <SidebarNodeItem
                      key={node.id}
                      node={node}
                      onSelect={handleNodeSelect}
                    />
                  ))}
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="favorites" className="flex-1 mt-0">
              <ScrollArea className={scrollAreaClass}>
                {favoriteNodes.length > 0 ? (
                  <div className="p-3 space-y-2">
                    {favoriteNodes.map((node) => (
                      <SidebarNodeItem
                        key={node.id}
                        node={node}
                        onSelect={handleNodeSelect}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="flex items-center justify-center h-full text-muted-foreground p-4">
                    No favorite nodes yet
                  </div>
                )}
              </ScrollArea>
            </TabsContent>
          </Tabs>
        </>
      )}

      {isCollapsed && (
        <div className="flex flex-col items-center gap-4 py-4">
          {nodeCategories.map((category) => (
            <Button
              key={category.id}
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              title={category.name}
              onClick={handleCategoryClick}
            >
              {category.icon}
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}

const filterCategories = (
  categories: NodeCategory[],
  query: string,
): NodeCategory[] => {
  const normalizedQuery = query.toLowerCase();
  if (!normalizedQuery) {
    return categories;
  }

  return categories
    .map((category) => ({
      ...category,
      nodes: category.nodes.filter(
        (node) =>
          node.name.toLowerCase().includes(normalizedQuery) ||
          node.description.toLowerCase().includes(normalizedQuery),
      ),
    }))
    .filter((category) => category.nodes.length > 0);
};
