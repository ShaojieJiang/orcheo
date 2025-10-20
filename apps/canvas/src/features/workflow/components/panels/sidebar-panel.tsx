import React from "react";
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
import {
  Search,
  ChevronLeft,
  Globe,
  Code,
  Zap,
  Database,
  Sparkles,
  MessageSquare,
  Mail,
  FileText,
  Clock,
  Calendar,
  Briefcase,
  GitBranch,
  RotateCw,
  Settings,
  Filter,
  AlertCircle,
  BarChart,
  PieChart,
  LineChart,
  Play,
  Square,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NodeCategory {
  id: string;
  name: string;
  icon: React.ReactNode;
  nodes: {
    id: string;
    name: string;
    description: string;
    icon: React.ReactNode;
    type: string;
    data: {
      label: string;
      type: string;
      description: string;
    };
  }[];
}

type SidebarNode = NodeCategory["nodes"][number];

interface SidebarPanelProps {
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  onAddNode?: (node: SidebarNode) => void;
  className?: string;
  position?: "left" | "canvas";
  searchQuery?: string;
  onSearchQueryChange?: (value: string) => void;
}

export default function SidebarPanel({
  isCollapsed = false,
  onToggleCollapse,
  onAddNode,
  className,
  position = "left",
  searchQuery = "",
  onSearchQueryChange,
}: SidebarPanelProps) {
  const nodeCategories: NodeCategory[] = [
    {
      id: "special",
      name: "Special Nodes",
      icon: <Settings className="h-4 w-4 text-gray-500" />,

      nodes: [
        {
          id: "start-node",
          name: "Workflow Start",
          description: "Beginning of the workflow",
          icon: <Play className="h-4 w-4 text-emerald-600" />,

          type: "start",
          data: {
            label: "Workflow Start",
            type: "start",
            description: "Beginning of the workflow",
          },
        },
        {
          id: "end-node",
          name: "Workflow End",
          description: "End of the workflow",
          icon: <Square className="h-4 w-4 text-rose-600" />,

          type: "end",
          data: {
            label: "Workflow End",
            type: "end",
            description: "End of the workflow",
          },
        },
        {
          id: "group-node",
          name: "Node Group",
          description: "Group related nodes together",
          icon: <Briefcase className="h-4 w-4 text-blue-500" />,

          type: "group",
          data: {
            label: "Node Group",
            type: "group",
            description: "Group related nodes together",
          },
        },
      ],
    },
    {
      id: "triggers",
      name: "Triggers",
      icon: <Zap className="h-4 w-4 text-amber-500" />,

      nodes: [
        {
          id: "webhook-trigger",
          name: "Webhook",
          description: "Trigger workflow via HTTP request",
          icon: <Globe className="h-4 w-4 text-amber-500" />,

          type: "trigger",
          data: {
            label: "Webhook",
            type: "trigger",
            description: "Trigger workflow via HTTP request",
          },
        },
        {
          id: "schedule-trigger",
          name: "Schedule",
          description: "Run workflow on a schedule",
          icon: <Clock className="h-4 w-4 text-amber-500" />,

          type: "trigger",
          data: {
            label: "Schedule",
            type: "trigger",
            description: "Run workflow on a schedule",
          },
        },
        {
          id: "calendar-trigger",
          name: "Calendar",
          description: "Trigger on calendar events",
          icon: <Calendar className="h-4 w-4 text-amber-500" />,

          type: "trigger",
          data: {
            label: "Calendar",
            type: "trigger",
            description: "Trigger on calendar events",
          },
        },
        {
          id: "chat-trigger",
          name: "Chat Trigger",
          description: "Trigger workflow from chat interactions",
          icon: <MessageSquare className="h-4 w-4 text-amber-500" />,

          type: "chatTrigger",
          data: {
            label: "Chat Trigger",
            type: "chatTrigger",
            description: "Trigger workflow from chat interactions",
          },
        },
      ],
    },
    {
      id: "actions",
      name: "Actions",
      icon: <Globe className="h-4 w-4 text-blue-500" />,

      nodes: [
        {
          id: "http-request",
          name: "HTTP Request",
          description: "Make HTTP requests to external APIs",
          icon: <Globe className="h-4 w-4 text-blue-500" />,

          type: "api",
          data: {
            label: "HTTP Request",
            type: "api",
            description: "Make HTTP requests to external APIs",
          },
        },
        {
          id: "email-send",
          name: "Send Email",
          description: "Send and receive emails",
          icon: <Mail className="h-4 w-4 text-blue-500" />,

          type: "api",
          data: {
            label: "Send Email",
            type: "api",
            description: "Send and receive emails",
          },
        },
        {
          id: "slack",
          name: "Slack",
          description: "Interact with Slack channels",
          icon: <MessageSquare className="h-4 w-4 text-blue-500" />,

          type: "api",
          data: {
            label: "Slack",
            type: "api",
            description: "Interact with Slack channels",
          },
        },
      ],
    },
    {
      id: "logic",
      name: "Logic & Flow",
      icon: <GitBranch className="h-4 w-4 text-purple-500" />,

      nodes: [
        {
          id: "condition",
          name: "Condition",
          description: "Branch based on condition",
          icon: <GitBranch className="h-4 w-4 text-purple-500" />,

          type: "function",
          data: {
            label: "Condition",
            type: "function",
            description: "Branch based on condition",
          },
        },
        {
          id: "loop",
          name: "Loop",
          description: "Iterate over items",
          icon: <RotateCw className="h-4 w-4 text-purple-500" />,

          type: "function",
          data: {
            label: "Loop",
            type: "function",
            description: "Iterate over items",
          },
        },
        {
          id: "switch",
          name: "Switch",
          description: "Multiple conditional branches",
          icon: <Filter className="h-4 w-4 text-purple-500" />,

          type: "function",
          data: {
            label: "Switch",
            type: "function",
            description: "Multiple conditional branches",
          },
        },
        {
          id: "delay",
          name: "Delay",
          description: "Pause workflow execution",
          icon: <Clock className="h-4 w-4 text-purple-500" />,

          type: "function",
          data: {
            label: "Delay",
            type: "function",
            description: "Pause workflow execution",
          },
        },
        {
          id: "error-handler",
          name: "Error Handler",
          description: "Handle errors in workflow",
          icon: <AlertCircle className="h-4 w-4 text-purple-500" />,

          type: "function",
          data: {
            label: "Error Handler",
            type: "function",
            description: "Handle errors in workflow",
          },
        },
      ],
    },
    {
      id: "data",
      name: "Data Processing",
      icon: <Database className="h-4 w-4 text-green-500" />,

      nodes: [
        {
          id: "database",
          name: "Database",
          description: "Query databases with SQL",
          icon: <Database className="h-4 w-4 text-green-500" />,

          type: "data",
          data: {
            label: "Database",
            type: "data",
            description: "Query databases with SQL",
          },
        },
        {
          id: "transform",
          name: "Transform",
          description: "Transform data between steps",
          icon: <Code className="h-4 w-4 text-green-500" />,

          type: "data",
          data: {
            label: "Transform",
            type: "data",
            description: "Transform data between steps",
          },
        },
        {
          id: "filter",
          name: "Filter Data",
          description: "Filter data based on conditions",
          icon: <Filter className="h-4 w-4 text-green-500" />,

          type: "data",
          data: {
            label: "Filter Data",
            type: "data",
            description: "Filter data based on conditions",
          },
        },
        {
          id: "aggregate",
          name: "Aggregate",
          description: "Group and aggregate data",
          icon: <BarChart className="h-4 w-4 text-green-500" />,

          type: "data",
          data: {
            label: "Aggregate",
            type: "data",
            description: "Group and aggregate data",
          },
        },
      ],
    },
    {
      id: "ai",
      name: "AI & ML",
      icon: <Sparkles className="h-4 w-4 text-indigo-500" />,

      nodes: [
        {
          id: "text-generation",
          name: "Text Generation",
          description: "Generate text with AI models",
          icon: <FileText className="h-4 w-4 text-indigo-500" />,

          type: "ai",
          data: {
            label: "Text Generation",
            type: "ai",
            description: "Generate text with AI models",
          },
        },
        {
          id: "chat-completion",
          name: "Chat Completion",
          description: "Generate chat responses",
          icon: <MessageSquare className="h-4 w-4 text-indigo-500" />,

          type: "ai",
          data: {
            label: "Chat Completion",
            type: "ai",
            description: "Generate chat responses",
          },
        },
        {
          id: "classification",
          name: "Classification",
          description: "Classify content with ML models",
          icon: <Sparkles className="h-4 w-4 text-indigo-500" />,

          type: "ai",
          data: {
            label: "Classification",
            type: "ai",
            description: "Classify content with ML models",
          },
        },
        {
          id: "image-generation",
          name: "Image Generation",
          description: "Generate images with AI",
          icon: <Sparkles className="h-4 w-4 text-indigo-500" />,

          type: "ai",
          data: {
            label: "Image Generation",
            type: "ai",
            description: "Generate images with AI",
          },
        },
      ],
    },
    {
      id: "visualization",
      name: "Visualization",
      icon: <BarChart className="h-4 w-4 text-orange-500" />,

      nodes: [
        {
          id: "bar-chart",
          name: "Bar Chart",
          description: "Create bar charts from data",
          icon: <BarChart className="h-4 w-4 text-orange-500" />,

          type: "visualization",
          data: {
            label: "Bar Chart",
            type: "visualization",
            description: "Create bar charts from data",
          },
        },
        {
          id: "line-chart",
          name: "Line Chart",
          description: "Create line charts from data",
          icon: <LineChart className="h-4 w-4 text-orange-500" />,

          type: "visualization",
          data: {
            label: "Line Chart",
            type: "visualization",
            description: "Create line charts from data",
          },
        },
        {
          id: "pie-chart",
          name: "Pie Chart",
          description: "Create pie charts from data",
          icon: <PieChart className="h-4 w-4 text-orange-500" />,

          type: "visualization",
          data: {
            label: "Pie Chart",
            type: "visualization",
            description: "Create pie charts from data",
          },
        },
      ],
    },
  ];

  const recentNodes = [
    {
      id: "http-recent",
      name: "HTTP Request",
      description: "Make HTTP requests to external APIs",
      icon: <Globe className="h-4 w-4 text-blue-500" />,

      type: "api",
      data: {
        label: "HTTP Request",
        type: "api",
        description: "Make HTTP requests to external APIs",
      },
    },
    {
      id: "code-recent",
      name: "Code",
      description: "Execute custom JavaScript code",
      icon: <Code className="h-4 w-4 text-purple-500" />,

      type: "function",
      data: {
        label: "Code",
        type: "function",
        description: "Execute custom JavaScript code",
      },
    },
    {
      id: "text-generation-recent",
      name: "Text Generation",
      description: "Generate text with AI models",
      icon: <Sparkles className="h-4 w-4 text-indigo-500" />,

      type: "ai",
      data: {
        label: "Text Generation",
        type: "ai",
        description: "Generate text with AI models",
      },
    },
    {
      id: "start-node-recent",
      name: "Workflow Start",
      description: "Beginning of the workflow",
      icon: <Play className="h-4 w-4 text-emerald-600" />,

      type: "start",
      data: {
        label: "Workflow Start",
        type: "start",
        description: "Beginning of the workflow",
      },
    },
    {
      id: "end-node-recent",
      name: "Workflow End",
      description: "End of the workflow",
      icon: <Square className="h-4 w-4 text-rose-600" />,

      type: "end",
      data: {
        label: "Workflow End",
        type: "end",
        description: "End of the workflow",
      },
    },
  ];

  const favoriteNodes = [
    {
      id: "http-favorite",
      name: "HTTP Request",
      description: "Make HTTP requests to external APIs",
      icon: <Globe className="h-4 w-4 text-blue-500" />,

      type: "api",
      data: {
        label: "HTTP Request",
        type: "api",
        description: "Make HTTP requests to external APIs",
      },
    },
    {
      id: "transform-favorite",
      name: "Transform",
      description: "Transform data between steps",
      icon: <Code className="h-4 w-4 text-purple-500" />,

      type: "data",
      data: {
        label: "Transform",
        type: "data",
        description: "Transform data between steps",
      },
    },
  ];

  const normalizedQuery = searchQuery.toLowerCase();

  const filteredCategories = nodeCategories
    .map((category) => ({
      ...category,
      nodes: category.nodes.filter(
        (node) =>
          node.name.toLowerCase().includes(normalizedQuery) ||
          node.description.toLowerCase().includes(normalizedQuery),
      ),
    }))
    .filter(
      (category) => category.nodes.length > 0 || normalizedQuery.length === 0,
    );

  const handleNodeClick = (node: SidebarNode) => {
    onAddNode?.(node);
  };

  const handleCategoryClick = () => {
    if (isCollapsed && onToggleCollapse) {
      onToggleCollapse();
    }
  };

  const NodeItem = ({
    node,
    onClick,
  }: {
    node: SidebarNode;
    onClick?: () => void;
  }) => (
    <div
      className="flex items-start gap-3 p-2 rounded-md hover:bg-accent cursor-pointer"
      onClick={() => {
        handleNodeClick(node);
        if (onClick) onClick();
      }}
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("application/reactflow", JSON.stringify(node));
        e.dataTransfer.effectAllowed = "move";
      }}
    >
      <div className="mt-0.5">{node.icon}</div>
      <div>
        <div className="font-medium text-sm">{node.name}</div>
        <div className="text-xs text-muted-foreground">{node.description}</div>
      </div>
    </div>
  );

  // Determine the appropriate classes based on position
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
                onChange={(e) => onSearchQueryChange?.(e.target.value)}
                aria-label="Filter node catalog"
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
              <ScrollArea
                className={
                  position === "canvas"
                    ? "h-[calc(100vh-280px)]"
                    : "h-[calc(100vh-180px)]"
                }
              >
                <div className="p-3">
                  {searchQuery && filteredCategories.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      No nodes found matching "{searchQuery}"
                    </div>
                  ) : (
                    <Accordion
                      type="multiple"
                      defaultValue={nodeCategories.map((c) => c.id)}
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
                                <NodeItem key={node.id} node={node} />
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
              <ScrollArea
                className={
                  position === "canvas"
                    ? "h-[calc(100vh-280px)]"
                    : "h-[calc(100vh-180px)]"
                }
              >
                <div className="p-3 space-y-2">
                  {recentNodes.map((node) => (
                    <NodeItem key={node.id} node={node} />
                  ))}
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="favorites" className="flex-1 mt-0">
              <ScrollArea
                className={
                  position === "canvas"
                    ? "h-[calc(100vh-280px)]"
                    : "h-[calc(100vh-180px)]"
                }
              >
                {favoriteNodes.length > 0 ? (
                  <div className="p-3 space-y-2">
                    {favoriteNodes.map((node) => (
                      <NodeItem key={node.id} node={node} />
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
