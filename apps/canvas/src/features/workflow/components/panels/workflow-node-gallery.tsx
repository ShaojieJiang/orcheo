import React, { useState } from "react";
import { cn } from "@/lib/utils";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/design-system/ui/tabs";
import { Input } from "@/design-system/ui/input";
import { ScrollArea } from "@/design-system/ui/scroll-area";
import { Search } from "lucide-react";
import WorkflowNode from "@features/workflow/components/nodes/workflow-node";
import StartEndNode from "@features/workflow/components/nodes/start-end-node";
import GroupNode from "@features/workflow/components/nodes/group-node";
import {
  Globe,
  Code,
  Zap,
  Database,
  Sparkles,
  FileText,
  MessageSquare,
  Mail,
} from "lucide-react";

const NODE_CATEGORIES = {
  all: "All Nodes",
  special: "Special Nodes",
  triggers: "Triggers",
  actions: "Actions",
  logic: "Logic & Flow",
  data: "Data Processing",
  ai: "AI & ML",
};

export default function WorkflowNodeGallery() {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState("all");

  // Define all available nodes
  const allNodes = [
    // Special nodes
    {
      id: "start-node",
      category: "special",
      component: (
        <StartEndNode
          id="start-node"
          data={{
            label: "Workflow Start",
            type: "start",
            description: "Beginning of the workflow",
          }}
        />
      ),
    },
    {
      id: "end-node",
      category: "special",
      component: (
        <StartEndNode
          id="end-node"
          data={{
            label: "Workflow End",
            type: "end",
            description: "End of the workflow",
          }}
        />
      ),
    },
    {
      id: "group-node",
      category: "special",
      component: (
        <GroupNode
          id="group-node"
          data={{
            label: "Node Group",
            description: "Group related nodes together",
            nodeCount: 3,
            color: "blue",
          }}
        />
      ),
    },
    // Trigger nodes
    {
      id: "webhook-trigger",
      category: "triggers",
      component: (
        <WorkflowNode
          id="webhook-trigger"
          data={{
            label: "Webhook",
            description: "Trigger on HTTP webhook",
            icon: <Zap className="h-4 w-4 text-amber-500" />,

            type: "trigger",
          }}
        />
      ),
    },
    {
      id: "schedule-trigger",
      category: "triggers",
      component: (
        <WorkflowNode
          id="schedule-trigger"
          data={{
            label: "Schedule",
            description: "Trigger on schedule",
            icon: <Clock className="h-4 w-4 text-amber-500" />,

            type: "trigger",
          }}
        />
      ),
    },
    // Action nodes
    {
      id: "http-request",
      category: "actions",
      component: (
        <WorkflowNode
          id="http-request"
          data={{
            label: "HTTP Request",
            description: "Make HTTP requests",
            icon: <Globe className="h-4 w-4 text-blue-500" />,

            type: "api",
          }}
        />
      ),
    },
    {
      id: "email-send",
      category: "actions",
      component: (
        <WorkflowNode
          id="email-send"
          data={{
            label: "Send Email",
            description: "Send an email",
            icon: <Mail className="h-4 w-4 text-blue-500" />,

            type: "api",
          }}
        />
      ),
    },
    // Logic nodes
    {
      id: "condition",
      category: "logic",
      component: (
        <WorkflowNode
          id="condition"
          data={{
            label: "Condition",
            description: "Branch based on condition",
            icon: <GitBranch className="h-4 w-4 text-purple-500" />,

            type: "function",
          }}
        />
      ),
    },
    {
      id: "loop",
      category: "logic",
      component: (
        <WorkflowNode
          id="loop"
          data={{
            label: "Loop",
            description: "Iterate over items",
            icon: <RotateCw className="h-4 w-4 text-purple-500" />,

            type: "function",
          }}
        />
      ),
    },
    // Data nodes
    {
      id: "transform",
      category: "data",
      component: (
        <WorkflowNode
          id="transform"
          data={{
            label: "Transform",
            description: "Transform data",
            icon: <Code className="h-4 w-4 text-green-500" />,

            type: "data",
          }}
        />
      ),
    },
    {
      id: "database",
      category: "data",
      component: (
        <WorkflowNode
          id="database"
          data={{
            label: "Database",
            description: "Query database",
            icon: <Database className="h-4 w-4 text-green-500" />,

            type: "data",
          }}
        />
      ),
    },
    // AI nodes
    {
      id: "text-generation",
      category: "ai",
      component: (
        <WorkflowNode
          id="text-generation"
          data={{
            label: "Text Generation",
            description: "Generate text with AI",
            icon: <FileText className="h-4 w-4 text-indigo-500" />,

            type: "ai",
          }}
        />
      ),
    },
    {
      id: "chat-completion",
      category: "ai",
      component: (
        <WorkflowNode
          id="chat-completion"
          data={{
            label: "Chat Completion",
            description: "Generate chat responses",
            icon: <MessageSquare className="h-4 w-4 text-indigo-500" />,

            type: "ai",
          }}
        />
      ),
    },
  ];

  // Filter nodes based on search query and active category
  const filteredNodes = allNodes.filter((node) => {
    const matchesSearch =
      searchQuery === "" ||
      node.id.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesCategory =
      activeCategory === "all" || node.category === activeCategory;

    return matchesSearch && matchesCategory;
  });

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

// Import missing icons
import { Clock, GitBranch, RotateCw } from "lucide-react";
