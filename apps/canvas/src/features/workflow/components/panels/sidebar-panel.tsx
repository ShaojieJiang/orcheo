import React, { useState } from "react";
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
  Zap,
  Database,
  Sparkles,
  GitBranch,
  Settings,
  BarChart,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  getNodeIcon,
  type NodeIconKey,
} from "@features/workflow/lib/node-icons";
import { DEFAULT_PYTHON_CODE } from "@features/workflow/lib/python-node";

interface NodeCategory {
  id: string;
  name: string;
  icon: React.ReactNode;
  nodes: {
    id: string;
    name: string;
    description: string;
    iconKey: NodeIconKey;
    icon?: React.ReactNode;
    type: string;
    backendType?: string;
    data: {
      label: string;
      type: string;
      description: string;
      iconKey: NodeIconKey;
      backendType?: string;
      [key: string]: unknown;
    };
  }[];
}

type SidebarNode = NodeCategory["nodes"][number];

const buildSidebarNode = ({
  id,
  name,
  description,
  iconKey,
  type,
  backendType,
  data,
}: {
  id: string;
  name: string;
  description: string;
  iconKey: NodeIconKey;
  type: string;
  backendType?: string;
  data?: Record<string, unknown>;
}): SidebarNode => {
  const mergedData: NodeCategory["nodes"][number]["data"] = {
    label: name,
    type,
    description,
    ...(data ?? {}),
    iconKey,
    ...(backendType ? { backendType } : {}),
  };

  return {
    id,
    name,
    description,
    iconKey,
    icon: getNodeIcon(iconKey),
    type,
    backendType,
    data: mergedData,
  };
};

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

  const nodeCategories: NodeCategory[] = [
    {
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
    },
    {
      id: "triggers",
      name: "Triggers",
      icon: <Zap className="h-4 w-4 text-amber-500" />,

      nodes: [
        buildSidebarNode({
          id: "webhook-trigger",
          name: "Webhook",
          description: "Trigger workflow via HTTP request",
          iconKey: "webhook",
          type: "trigger",
          backendType: "WebhookTriggerNode",
        }),
        buildSidebarNode({
          id: "manual-trigger",
          name: "Manual",
          description: "Dispatch runs from the dashboard",
          iconKey: "manualTrigger",
          type: "trigger",
          backendType: "ManualTriggerNode",
        }),
        buildSidebarNode({
          id: "http-polling-trigger",
          name: "HTTP Polling",
          description: "Poll an API on a schedule",
          iconKey: "httpPolling",
          type: "trigger",
          backendType: "HttpPollingTriggerNode",
        }),
        buildSidebarNode({
          id: "schedule-trigger",
          name: "Schedule",
          description: "Run workflow on a schedule",
          iconKey: "schedule",
          type: "trigger",
          backendType: "CronTriggerNode",
        }),
      ],
    },
    {
      id: "actions",
      name: "Actions",
      icon: <Globe className="h-4 w-4 text-blue-500" />,

      nodes: [
        buildSidebarNode({
          id: "http-request",
          name: "HTTP Request",
          description: "Make HTTP requests to external APIs",
          iconKey: "http",
          type: "api",
        }),
        buildSidebarNode({
          id: "email-send",
          name: "Send Email",
          description: "Send and receive emails",
          iconKey: "email",
          type: "api",
        }),
        buildSidebarNode({
          id: "slack",
          name: "Slack",
          description: "Interact with Slack channels",
          iconKey: "slack",
          type: "api",
          backendType: "SlackNode",
        }),
      ],
    },
    {
      id: "logic",
      name: "Logic & Flow",
      icon: <GitBranch className="h-4 w-4 text-purple-500" />,

      nodes: [
        buildSidebarNode({
          id: "condition",
          name: "If / Else",
          description: "Branch based on a comparison",
          iconKey: "condition",
          type: "function",
          backendType: "IfElseNode",
          data: {
            conditionLogic: "and",
            conditions: [
              {
                id: "condition-1",
                left: "{{previous.result}}",
                operator: "equals",
                right: "expected",
                caseSensitive: false,
              },
            ],
            outputs: [
              { id: "true", label: "True" },
              { id: "false", label: "False" },
            ],
          },
        }),
        buildSidebarNode({
          id: "loop",
          name: "While Loop",
          description: "Iterate while a condition remains true",
          iconKey: "loop",
          type: "function",
          backendType: "WhileNode",
          data: {
            conditionLogic: "and",
            conditions: [
              {
                id: "condition-1",
                operator: "less_than",
                right: 3,
              },
            ],
            maxIterations: 10,
            outputs: [
              { id: "continue", label: "Continue" },
              { id: "exit", label: "Exit" },
            ],
          },
        }),
        buildSidebarNode({
          id: "switch",
          name: "Switch",
          description: "Multiple conditional branches",
          iconKey: "switch",
          type: "function",
          backendType: "SwitchNode",
          data: {
            value: "{{previous.status}}",
            caseSensitive: false,
            defaultBranchKey: "default",
            cases: [
              {
                id: "case-1",
                match: "approved",
                label: "Approved",
                branchKey: "approved",
              },
              {
                id: "case-2",
                match: "rejected",
                label: "Rejected",
                branchKey: "rejected",
              },
            ],
            outputs: [
              { id: "approved", label: "Approved" },
              { id: "rejected", label: "Rejected" },
              { id: "default", label: "Default" },
            ],
          },
        }),
        buildSidebarNode({
          id: "delay",
          name: "Delay",
          description: "Pause workflow execution",
          iconKey: "delay",
          type: "function",
          backendType: "DelayNode",
          data: {
            durationSeconds: 5,
          },
        }),
        buildSidebarNode({
          id: "error-handler",
          name: "Error Handler",
          description: "Handle errors in workflow",
          iconKey: "errorHandler",
          type: "function",
        }),
        buildSidebarNode({
          id: "set-variable",
          name: "Set Variable",
          description: "Store a value for downstream steps",
          iconKey: "setVariable",
          type: "function",
          backendType: "SetVariableNode",
          data: {
            variables: [
              {
                name: "my_variable",
                valueType: "string",
                value: "sample",
              },
            ],
            outputs: [{ id: "default" }],
          },
        }),
      ],
    },
    {
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
    },
    {
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
    },
    {
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
    },
  ];

  const recentNodes = [
    buildSidebarNode({
      id: "http-recent",
      name: "HTTP Request",
      description: "Make HTTP requests to external APIs",
      iconKey: "http",
      type: "api",
    }),
    buildSidebarNode({
      id: "python-recent",
      name: "Python Code",
      description: "Execute custom Python scripts",
      iconKey: "python",
      type: "python",
      data: {
        code: DEFAULT_PYTHON_CODE,
      },
    }),
    buildSidebarNode({
      id: "text-generation-recent",
      name: "Text Generation",
      description: "Generate text with AI models",
      iconKey: "textGeneration",
      type: "ai",
    }),
    buildSidebarNode({
      id: "start-node-recent",
      name: "Workflow Start",
      description: "Beginning of the workflow",
      iconKey: "start",
      type: "start",
    }),
    buildSidebarNode({
      id: "end-node-recent",
      name: "Workflow End",
      description: "End of the workflow",
      iconKey: "end",
      type: "end",
    }),
  ];

  const favoriteNodes = [
    buildSidebarNode({
      id: "http-favorite",
      name: "HTTP Request",
      description: "Make HTTP requests to external APIs",
      iconKey: "http",
      type: "api",
    }),
    buildSidebarNode({
      id: "transform-favorite",
      name: "Transform",
      description: "Transform data between steps",
      iconKey: "transform",
      type: "data",
    }),
    buildSidebarNode({
      id: "python-favorite",
      name: "Python Code",
      description: "Execute custom Python scripts",
      iconKey: "python",
      type: "python",
      data: {
        code: DEFAULT_PYTHON_CODE,
      },
    }),
  ];

  const filteredCategories = nodeCategories
    .map((category) => ({
      ...category,
      nodes: category.nodes.filter(
        (node) =>
          node.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          node.description.toLowerCase().includes(searchQuery.toLowerCase()),
      ),
    }))
    .filter((category) => category.nodes.length > 0);

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
  }) => {
    const icon = node.icon ?? getNodeIcon(node.iconKey);
    return (
      <div
        className="flex items-start gap-3 p-2 rounded-md hover:bg-accent cursor-pointer"
        onClick={() => {
          handleNodeClick(node);
          if (onClick) onClick();
        }}
        draggable
        onDragStart={(e) => {
          const serializableNode = { ...node, icon: undefined };
          e.dataTransfer.setData(
            "application/reactflow",
            JSON.stringify(serializableNode),
          );
          e.dataTransfer.effectAllowed = "move";
        }}
      >
        <div className="mt-0.5">{icon}</div>
        <div>
          <div className="font-medium text-sm">{node.name}</div>
          <div className="text-xs text-muted-foreground">
            {node.description}
          </div>
        </div>
      </div>
    );
  };

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
                onChange={(e) => setSearchQuery(e.target.value)}
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
