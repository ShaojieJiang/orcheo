import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { Badge } from "@/design-system/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/design-system/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/design-system/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/design-system/ui/tabs";
import {
  Search,
  Plus,
  FolderPlus,
  Clock,
  CheckCircle,
  AlertCircle,
  MoreHorizontal,
  Copy,
  Download,
  Trash,
  Pencil,
  Star,
  Filter,
  ArrowUpDown,
  Zap,
  Loader2,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/design-system/ui/dialog";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/design-system/ui/popover";
import { Checkbox } from "@/design-system/ui/checkbox";
import { Label } from "@/design-system/ui/label";

import TopNavigation from "@features/shared/components/top-navigation";
import { toast } from "@/hooks/use-toast";
import {
  createWorkflow,
  createWorkflowVersion,
  listWorkflows,
  listWorkflowVersions,
} from "@features/workflow/api/client";
import type {
  CanvasGraphDefinition,
  CanvasGraphEdge,
  CanvasGraphNode,
  WorkflowSummary,
} from "@features/workflow/api/types";
import {
  WORKFLOW_TEMPLATES,
  type Workflow as GalleryWorkflow,
} from "@features/workflow/data/workflow-data";

const CANVAS_GRAPH_FORMAT = "reactflow@1" as const;
const VALID_NODE_STATUSES = new Set(["idle", "running", "success", "error"]);

function createAvatarUrl(actor: string): string {
  const slug = encodeURIComponent(actor || "system");
  return `https://avatar.vercel.sh/${slug}`;
}

function deriveOwner(summary: WorkflowSummary): GalleryWorkflow["owner"] {
  const actor = summary.audit_log?.[0]?.actor?.trim() || "system";
  const displayName = actor.charAt(0).toUpperCase() + actor.slice(1);
  return {
    id: actor,
    name: displayName,
    avatar: createAvatarUrl(actor),
  };
}

function normaliseNodes(
  nodes: CanvasGraphNode[] | undefined,
): GalleryWorkflow["nodes"] {
  if (!Array.isArray(nodes)) {
    return [];
  }
  return nodes
    .map((node, index) => {
      if (!node || typeof node !== "object") {
        return null;
      }
      const id =
        typeof node.id === "string" && node.id ? node.id : `node-${index + 1}`;
      const type =
        typeof node.type === "string" && node.type ? node.type : "default";
      const position =
        node.position && typeof node.position === "object"
          ? {
              x: typeof node.position.x === "number" ? node.position.x : 0,
              y: typeof node.position.y === "number" ? node.position.y : 0,
            }
          : { x: 0, y: 0 };
      const rawStatus =
        node.data && typeof node.data.status === "string"
          ? node.data.status
          : undefined;
      const status =
        rawStatus && VALID_NODE_STATUSES.has(rawStatus) ? rawStatus : "idle";
      const label =
        node.data && typeof node.data.label === "string" ? node.data.label : id;
      const description =
        node.data && typeof node.data.description === "string"
          ? node.data.description
          : undefined;
      return {
        id,
        type,
        position,
        data: {
          label,
          description,
          status: status as GalleryWorkflow["nodes"][number]["data"]["status"],
        },
      };
    })
    .filter((node): node is GalleryWorkflow["nodes"][number] => node !== null);
}

function normaliseEdges(
  edges: CanvasGraphEdge[] | undefined,
): GalleryWorkflow["edges"] {
  if (!Array.isArray(edges)) {
    return [];
  }
  return edges
    .map((edge, index) => {
      if (!edge || typeof edge !== "object") {
        return null;
      }
      const source = typeof edge.source === "string" ? edge.source : "";
      const target = typeof edge.target === "string" ? edge.target : "";
      if (!source || !target) {
        return null;
      }
      return {
        id:
          typeof edge.id === "string" && edge.id
            ? edge.id
            : `edge-${index + 1}`,
        source,
        target,
        sourceHandle:
          typeof edge.sourceHandle === "string" || edge.sourceHandle === null
            ? (edge.sourceHandle ?? null)
            : null,
        targetHandle:
          typeof edge.targetHandle === "string" || edge.targetHandle === null
            ? (edge.targetHandle ?? null)
            : null,
        label: typeof edge.label === "string" ? edge.label : undefined,
        type: typeof edge.type === "string" ? edge.type : undefined,
        animated: Boolean(edge.animated),
        style:
          edge.style && typeof edge.style === "object"
            ? (edge.style as Record<string, unknown>)
            : undefined,
      };
    })
    .filter((edge): edge is GalleryWorkflow["edges"][number] => edge !== null);
}

async function buildGalleryWorkflow(
  summary: WorkflowSummary,
): Promise<GalleryWorkflow> {
  let nodes: GalleryWorkflow["nodes"] = [];
  let edges: GalleryWorkflow["edges"] = [];
  try {
    const versions = await listWorkflowVersions(summary.id);
    const latest = versions.at(-1);
    if (
      latest &&
      latest.graph &&
      (!latest.graph.format || latest.graph.format === CANVAS_GRAPH_FORMAT)
    ) {
      nodes = normaliseNodes(latest.graph.nodes);
      edges = normaliseEdges(latest.graph.edges);
    }
  } catch (error) {
    console.error(`Failed to load versions for workflow ${summary.id}:`, error);
  }
  return {
    id: summary.id,
    name: summary.name,
    description: summary.description ?? undefined,
    createdAt: summary.created_at,
    updatedAt: summary.updated_at,
    owner: deriveOwner(summary),
    tags: summary.tags,
    lastRun: undefined,
    nodes,
    edges,
  };
}

function buildGraphFromTemplate(
  template: GalleryWorkflow,
): CanvasGraphDefinition {
  return {
    format: CANVAS_GRAPH_FORMAT,
    nodes: template.nodes.map((node) => ({
      id: node.id,
      type: node.type,
      position: node.position,
      data: {
        label: node.data.label,
        description: node.data.description,
        status: node.data.status,
      },
    })),
    edges: template.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.sourceHandle ?? null,
      targetHandle: edge.targetHandle ?? null,
      label: edge.label,
      type: edge.type,
      animated: edge.animated,
      style: edge.style,
    })),
  };
}

export default function WorkflowGallery() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTab, setSelectedTab] = useState("all");
  const [sortBy, setSortBy] = useState("updated");
  const [newFolderName, setNewFolderName] = useState("");
  const [newWorkflowName, setNewWorkflowName] = useState("");
  const [showNewFolderDialog, setShowNewFolderDialog] = useState(false);
  const [showNewWorkflowDialog, setShowNewWorkflowDialog] = useState(false);
  const [showFilterPopover, setShowFilterPopover] = useState(false);
  const [filters, setFilters] = useState({
    owner: {
      me: true,
      shared: true,
    },
    status: {
      active: true,
      draft: true,
      archived: false,
    },
    tags: {
      favorite: false,
      template: false,
      production: false,
      development: false,
    },
  });

  const [workflows, setWorkflows] = useState<GalleryWorkflow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isCreatingWorkflow, setIsCreatingWorkflow] = useState(false);
  const [activeTemplateId, setActiveTemplateId] = useState<string | null>(null);

  const loadWorkflows = useCallback(async () => {
    setIsLoading(true);
    try {
      const summaries = await listWorkflows();
      const items = await Promise.all(
        summaries.map((summary) => buildGalleryWorkflow(summary)),
      );
      setWorkflows(items);
      setError(null);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Unable to load workflows.";
      setError(message);
      toast({
        title: "Failed to load workflows",
        description: message,
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadWorkflows();
  }, [loadWorkflows]);

  // Filter workflows based on search query and selected tab
  const filteredWorkflows = useMemo(() => {
    const query = searchQuery.toLowerCase();
    return workflows.filter((workflow) => {
      const matchesSearch =
        workflow.name.toLowerCase().includes(query) ||
        (workflow.description &&
          workflow.description.toLowerCase().includes(query));
      if (selectedTab === "all") return matchesSearch;
      if (selectedTab === "favorites")
        return matchesSearch && workflow.tags.includes("favorite");
      if (selectedTab === "shared")
        return matchesSearch && workflow.owner.id !== "user-1";
      if (selectedTab === "templates")
        return matchesSearch && workflow.tags.includes("template");
      return matchesSearch;
    });
  }, [workflows, searchQuery, selectedTab]);

  // Sort workflows
  const sortedWorkflows = useMemo(() => {
    return [...filteredWorkflows].sort((a, b) => {
      if (sortBy === "name") return a.name.localeCompare(b.name);
      if (sortBy === "updated")
        return (
          new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        );
      if (sortBy === "created")
        return (
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        );
      return 0;
    });
  }, [filteredWorkflows, sortBy]);

  const handleCreateFolder = () => {
    // In a real app, this would create a folder in the backend
    toast({
      title: "Folder creation coming soon",
      description: newFolderName
        ? `We'll create "${newFolderName}" once persistence is wired up.`
        : "Folder creation will be available in a future update.",
    });
    setNewFolderName("");
    setShowNewFolderDialog(false);
    // You could add the new folder to state here
  };

  const handleCreateWorkflow = async () => {
    const trimmedName = newWorkflowName.trim();
    const name = trimmedName || "Untitled Workflow";
    setIsCreatingWorkflow(true);
    try {
      const created = await createWorkflow({
        name,
      });
      setShowNewWorkflowDialog(false);
      setNewWorkflowName("");
      toast({
        title: "Workflow created",
        description: `"${created.name}" is ready in your workspace.`,
      });
      await loadWorkflows();
      navigate(`/workflow-canvas/${created.id}`);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Unable to create workflow.";
      toast({
        title: "Failed to create workflow",
        description: message,
        variant: "destructive",
      });
    } finally {
      setIsCreatingWorkflow(false);
    }
  };

  const handleUseTemplate = async (template: GalleryWorkflow) => {
    setActiveTemplateId(template.id);
    try {
      const created = await createWorkflow({
        name: template.name,
        description: template.description,
        tags: template.tags.filter((tag) => tag !== "template"),
      });
      await createWorkflowVersion(created.id, {
        graph: buildGraphFromTemplate(template),
        metadata: { source: "template", template_id: template.id },
        notes: template.description ?? null,
      });
      toast({
        title: "Template imported",
        description: `Created "${created.name}" from template.`,
      });
      await loadWorkflows();
      navigate(`/workflow-canvas/${created.id}`);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Unable to import template.";
      toast({
        title: "Template import failed",
        description: message,
        variant: "destructive",
      });
    } finally {
      setActiveTemplateId(null);
    }
  };

  const handleApplyFilters = () => {
    toast({
      title: "Filters applied",
      description:
        "Filter changes will affect the gallery once data wiring is complete.",
    });
    setShowFilterPopover(false);
    // In a real app, this would update the filtered workflows
  };

  // Generate a simple thumbnail preview for a workflow
  const WorkflowThumbnail: React.FC<{ workflow: GalleryWorkflow }> = ({
    workflow,
  }) => {
    const nodeColors = {
      trigger: "#f59e0b",
      api: "#3b82f6",
      function: "#8b5cf6",
      data: "#10b981",
      ai: "#6366f1",
    };

    return (
      <div className="w-full h-24 bg-muted/30 rounded-md overflow-hidden relative">
        <svg
          width="100%"
          height="100%"
          viewBox="0 0 200 100"
          className="absolute inset-0"
        >
          {/* Draw simplified nodes and connections */}
          {workflow.nodes.slice(0, 5).map((node, index) => {
            const x = 30 + (index % 3) * 70;
            const y = 30 + Math.floor(index / 3) * 40;
            const color = nodeColors[node.type] || "#99a1b3";

            return (
              <g key={node.id}>
                <rect
                  x={x - 15}
                  y={y - 10}
                  width={30}
                  height={20}
                  rx={4}
                  fill={color}
                  fillOpacity={0.3}
                  stroke={color}
                  strokeWidth={1}
                />
              </g>
            );
          })}

          {/* Draw simplified edges */}
          {workflow.edges.slice(0, 4).map((edge) => {
            const sourceIndex = workflow.nodes.findIndex(
              (n) => n.id === edge.source,
            );
            const targetIndex = workflow.nodes.findIndex(
              (n) => n.id === edge.target,
            );

            if (
              sourceIndex >= 0 &&
              targetIndex >= 0 &&
              sourceIndex < 5 &&
              targetIndex < 5
            ) {
              const sourceX = 30 + (sourceIndex % 3) * 70 + 15;
              const sourceY = 30 + Math.floor(sourceIndex / 3) * 40;
              const targetX = 30 + (targetIndex % 3) * 70 - 15;
              const targetY = 30 + Math.floor(targetIndex / 3) * 40;

              return (
                <path
                  key={edge.id}
                  d={`M${sourceX},${sourceY} C${sourceX + 20},${sourceY} ${targetX - 20},${targetY} ${targetX},${targetY}`}
                  stroke="#99a1b3"
                  strokeWidth={1}
                  fill="none"
                />
              );
            }
            return null;
          })}
        </svg>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-screen">
      <TopNavigation />

      <main className="flex-1 overflow-auto">
        <div className="h-full">
          <div className="flex flex-col h-[calc(100%-80px)]">
            {/* Main content */}
            <div className="flex-1 overflow-auto">
              <div className="flex flex-col md:flex-row gap-4 mb-6 items-start md:items-center p-4">
                <div className="flex items-center gap-2 md:order-2">
                  <Dialog
                    open={showNewFolderDialog}
                    onOpenChange={setShowNewFolderDialog}
                  >
                    <DialogTrigger asChild>
                      <Button variant="outline">
                        <FolderPlus className="mr-2 h-4 w-4" />
                        New Folder
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Create New Folder</DialogTitle>
                        <DialogDescription>
                          Enter a name for your new folder.
                        </DialogDescription>
                      </DialogHeader>
                      <div className="py-4">
                        <Label htmlFor="folder-name">Folder Name</Label>
                        <Input
                          id="folder-name"
                          value={newFolderName}
                          onChange={(e) => setNewFolderName(e.target.value)}
                          placeholder="My Workflows"
                          className="mt-2"
                        />
                      </div>
                      <DialogFooter>
                        <Button
                          variant="outline"
                          onClick={() => setShowNewFolderDialog(false)}
                        >
                          Cancel
                        </Button>
                        <Button onClick={handleCreateFolder}>
                          Create Folder
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>

                  <Dialog
                    open={showNewWorkflowDialog}
                    onOpenChange={setShowNewWorkflowDialog}
                  >
                    <DialogTrigger asChild>
                      <Button>
                        <Plus className="mr-2 h-4 w-4" />
                        Create Workflow
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Create New Workflow</DialogTitle>
                        <DialogDescription>
                          Enter a name for your new workflow.
                        </DialogDescription>
                      </DialogHeader>
                      <div className="py-4">
                        <Label htmlFor="workflow-name">Workflow Name</Label>
                        <Input
                          id="workflow-name"
                          value={newWorkflowName}
                          onChange={(e) => setNewWorkflowName(e.target.value)}
                          placeholder="My New Workflow"
                          className="mt-2"
                        />
                      </div>
                      <DialogFooter>
                        <Button
                          variant="outline"
                          onClick={() => setShowNewWorkflowDialog(false)}
                        >
                          Cancel
                        </Button>
                        <Button
                          onClick={handleCreateWorkflow}
                          disabled={isCreatingWorkflow}
                        >
                          {isCreatingWorkflow ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          ) : (
                            <Plus className="mr-2 h-4 w-4" />
                          )}
                          Create & Open
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                </div>

                <div className="relative flex-1 md:order-1">
                  <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />

                  <Input
                    placeholder="Search workflows..."
                    className="pl-10"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>

                <div className="flex items-center gap-2 md:order-3">
                  <Select value={sortBy} onValueChange={setSortBy}>
                    <SelectTrigger className="w-[180px]">
                      <SelectValue placeholder="Sort by" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="updated">
                        <div className="flex items-center">
                          <ArrowUpDown className="mr-2 h-4 w-4" />
                          Last Updated
                        </div>
                      </SelectItem>
                      <SelectItem value="created">
                        <div className="flex items-center">
                          <Clock className="mr-2 h-4 w-4" />
                          Creation Date
                        </div>
                      </SelectItem>
                      <SelectItem value="name">
                        <div className="flex items-center">
                          <ArrowUpDown className="mr-2 h-4 w-4" />
                          Name
                        </div>
                      </SelectItem>
                    </SelectContent>
                  </Select>

                  <Popover
                    open={showFilterPopover}
                    onOpenChange={setShowFilterPopover}
                  >
                    <PopoverTrigger asChild>
                      <Button variant="outline" size="icon">
                        <Filter className="h-4 w-4" />
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-80">
                      <div className="space-y-4">
                        <h4 className="font-medium">Filter Workflows</h4>

                        <div className="space-y-2">
                          <h5 className="text-sm font-medium">Owner</h5>
                          <div className="flex flex-col gap-2">
                            <div className="flex items-center space-x-2">
                              <Checkbox
                                id="owner-me"
                                checked={filters.owner.me}
                                onCheckedChange={(checked) =>
                                  setFilters({
                                    ...filters,
                                    owner: { ...filters.owner, me: !!checked },
                                  })
                                }
                              />

                              <Label htmlFor="owner-me">Created by me</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                              <Checkbox
                                id="owner-shared"
                                checked={filters.owner.shared}
                                onCheckedChange={(checked) =>
                                  setFilters({
                                    ...filters,
                                    owner: {
                                      ...filters.owner,
                                      shared: !!checked,
                                    },
                                  })
                                }
                              />

                              <Label htmlFor="owner-shared">
                                Shared with me
                              </Label>
                            </div>
                          </div>
                        </div>

                        <div className="space-y-2">
                          <h5 className="text-sm font-medium">Status</h5>
                          <div className="flex flex-col gap-2">
                            <div className="flex items-center space-x-2">
                              <Checkbox
                                id="status-active"
                                checked={filters.status.active}
                                onCheckedChange={(checked) =>
                                  setFilters({
                                    ...filters,
                                    status: {
                                      ...filters.status,
                                      active: !!checked,
                                    },
                                  })
                                }
                              />

                              <Label htmlFor="status-active">Active</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                              <Checkbox
                                id="status-draft"
                                checked={filters.status.draft}
                                onCheckedChange={(checked) =>
                                  setFilters({
                                    ...filters,
                                    status: {
                                      ...filters.status,
                                      draft: !!checked,
                                    },
                                  })
                                }
                              />

                              <Label htmlFor="status-draft">Draft</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                              <Checkbox
                                id="status-archived"
                                checked={filters.status.archived}
                                onCheckedChange={(checked) =>
                                  setFilters({
                                    ...filters,
                                    status: {
                                      ...filters.status,
                                      archived: !!checked,
                                    },
                                  })
                                }
                              />

                              <Label htmlFor="status-archived">Archived</Label>
                            </div>
                          </div>
                        </div>

                        <div className="space-y-2">
                          <h5 className="text-sm font-medium">Tags</h5>
                          <div className="flex flex-col gap-2">
                            <div className="flex items-center space-x-2">
                              <Checkbox
                                id="tag-favorite"
                                checked={filters.tags.favorite}
                                onCheckedChange={(checked) =>
                                  setFilters({
                                    ...filters,
                                    tags: {
                                      ...filters.tags,
                                      favorite: !!checked,
                                    },
                                  })
                                }
                              />

                              <Label htmlFor="tag-favorite">Favorite</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                              <Checkbox
                                id="tag-template"
                                checked={filters.tags.template}
                                onCheckedChange={(checked) =>
                                  setFilters({
                                    ...filters,
                                    tags: {
                                      ...filters.tags,
                                      template: !!checked,
                                    },
                                  })
                                }
                              />

                              <Label htmlFor="tag-template">Template</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                              <Checkbox
                                id="tag-production"
                                checked={filters.tags.production}
                                onCheckedChange={(checked) =>
                                  setFilters({
                                    ...filters,
                                    tags: {
                                      ...filters.tags,
                                      production: !!checked,
                                    },
                                  })
                                }
                              />

                              <Label htmlFor="tag-production">Production</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                              <Checkbox
                                id="tag-development"
                                checked={filters.tags.development}
                                onCheckedChange={(checked) =>
                                  setFilters({
                                    ...filters,
                                    tags: {
                                      ...filters.tags,
                                      development: !!checked,
                                    },
                                  })
                                }
                              />

                              <Label htmlFor="tag-development">
                                Development
                              </Label>
                            </div>
                          </div>
                        </div>

                        <div className="flex justify-end gap-2 pt-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setShowFilterPopover(false)}
                          >
                            Cancel
                          </Button>
                          <Button size="sm" onClick={handleApplyFilters}>
                            Apply Filters
                          </Button>
                        </div>
                      </div>
                    </PopoverContent>
                  </Popover>
                </div>
              </div>

              <Tabs
                value={selectedTab}
                onValueChange={setSelectedTab}
                className="px-4"
              >
                <div className="flex justify-between items-center mb-6">
                  <TabsList>
                    <TabsTrigger value="all">All</TabsTrigger>
                    <TabsTrigger value="favorites">Favorites</TabsTrigger>
                    <TabsTrigger value="shared">Shared with me</TabsTrigger>
                    <TabsTrigger value="templates">Templates</TabsTrigger>
                  </TabsList>
                </div>

                <TabsContent value={selectedTab} className="mt-0">
                  {selectedTab === "templates" ? (
                    <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-3 pb-6">
                      {WORKFLOW_TEMPLATES.map((template) => (
                        <Card key={template.id} className="overflow-hidden">
                          <CardHeader className="pb-2 px-3 pt-3">
                            <CardTitle className="text-base">
                              {template.name}
                            </CardTitle>
                            <CardDescription className="line-clamp-2">
                              {template.description ||
                                "Use this template to get started quickly"}
                            </CardDescription>
                          </CardHeader>
                          <CardContent className="pb-2 px-3">
                            <WorkflowThumbnail workflow={template} />
                            <div className="flex flex-wrap gap-1 mt-2">
                              {template.tags.slice(0, 2).map((tag) => (
                                <Badge
                                  key={tag}
                                  variant="secondary"
                                  className="text-xs"
                                >
                                  {tag}
                                </Badge>
                              ))}
                            </div>
                          </CardContent>
                          <CardFooter className="flex justify-between items-center px-3 pb-3">
                            <div className="text-xs text-muted-foreground">
                              Updated{" "}
                              {new Date(
                                template.updatedAt,
                              ).toLocaleDateString()}
                            </div>
                            <Button
                              size="sm"
                              className="h-7 text-xs px-2"
                              onClick={() => handleUseTemplate(template)}
                              disabled={activeTemplateId === template.id}
                            >
                              {activeTemplateId === template.id ? (
                                <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                              ) : (
                                <Plus className="mr-2 h-3 w-3" />
                              )}
                              Use template
                            </Button>
                          </CardFooter>
                        </Card>
                      ))}
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {error && (
                        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                          {error}
                        </div>
                      )}
                      {isLoading ? (
                        <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
                          <Loader2 className="mb-4 h-6 w-6 animate-spin" />
                          Loading workflows…
                        </div>
                      ) : sortedWorkflows.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-12 text-center">
                          <div className="rounded-full bg-muted p-4 mb-4">
                            <Zap className="h-8 w-8 text-muted-foreground" />
                          </div>
                          <h3 className="text-lg font-medium mb-2">
                            No workflows found
                          </h3>
                          <p className="text-muted-foreground mb-6 max-w-md">
                            {searchQuery
                              ? `No workflows match your search for "${searchQuery}"`
                              : "Get started by creating your first workflow"}
                          </p>
                          <Button
                            onClick={() => setShowNewWorkflowDialog(true)}
                          >
                            <Plus className="mr-2 h-4 w-4" />
                            Create Workflow
                          </Button>
                        </div>
                      ) : (
                        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-3 pb-6">
                          {sortedWorkflows.map((workflow) => (
                            <Card key={workflow.id} className="overflow-hidden">
                              <CardHeader className="pb-2 px-3 pt-3">
                                <div className="flex justify-between items-start">
                                  <CardTitle className="text-base">
                                    {workflow.name}
                                  </CardTitle>
                                  <DropdownMenu>
                                    <DropdownMenuTrigger asChild>
                                      <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-7 w-7"
                                      >
                                        <MoreHorizontal className="h-4 w-4" />
                                      </Button>
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent align="end">
                                      <DropdownMenuItem
                                        onClick={() =>
                                          navigate(
                                            `/workflow-canvas/${workflow.id}`,
                                          )
                                        }
                                      >
                                        <Pencil className="mr-2 h-4 w-4" />
                                        Edit
                                      </DropdownMenuItem>
                                      <DropdownMenuItem>
                                        <Copy className="mr-2 h-4 w-4" />
                                        Duplicate
                                      </DropdownMenuItem>
                                      <DropdownMenuItem>
                                        <Download className="mr-2 h-4 w-4" />
                                        Export
                                      </DropdownMenuItem>
                                      <DropdownMenuSeparator />
                                      <DropdownMenuItem className="text-red-600">
                                        <Trash className="mr-2 h-4 w-4" />
                                        Delete
                                      </DropdownMenuItem>
                                    </DropdownMenuContent>
                                  </DropdownMenu>
                                </div>
                                <CardDescription className="line-clamp-1">
                                  {workflow.description ||
                                    "No description provided"}
                                </CardDescription>
                              </CardHeader>
                              <CardContent className="pb-2 px-3">
                                <WorkflowThumbnail workflow={workflow} />
                                <div className="flex flex-wrap gap-1 mt-2">
                                  {workflow.tags.slice(0, 2).map((tag) => (
                                    <Badge
                                      key={tag}
                                      variant="secondary"
                                      className="text-xs"
                                    >
                                      {tag}
                                    </Badge>
                                  ))}
                                  {workflow.tags.length > 2 && (
                                    <Badge
                                      variant="secondary"
                                      className="text-xs"
                                    >
                                      +{workflow.tags.length - 2} more
                                    </Badge>
                                  )}
                                </div>
                              </CardContent>
                              <CardFooter className="flex justify-between pt-2 px-3 pb-3">
                                <div className="flex items-center text-xs text-muted-foreground">
                                  <Avatar className="h-5 w-5 mr-1">
                                    <AvatarImage src={workflow.owner.avatar} />
                                    <AvatarFallback>
                                      {workflow.owner.name.charAt(0)}
                                    </AvatarFallback>
                                  </Avatar>
                                  <div className="flex items-center">
                                    <span className="mr-1">
                                      {new Date(
                                        workflow.updatedAt,
                                      ).toLocaleDateString()}
                                    </span>
                                    {workflow.lastRun && (
                                      <div className="flex items-center gap-1">
                                        {workflow.lastRun.status ===
                                          "success" && (
                                          <CheckCircle className="h-3 w-3 text-green-500" />
                                        )}
                                        {workflow.lastRun.status ===
                                          "error" && (
                                          <AlertCircle className="h-3 w-3 text-red-500" />
                                        )}
                                        {workflow.lastRun.status ===
                                          "running" && (
                                          <Clock className="h-3 w-3 text-blue-500 animate-pulse" />
                                        )}
                                      </div>
                                    )}
                                  </div>
                                </div>
                                <div className="flex gap-1">
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7"
                                  >
                                    <Star className="h-3 w-3" />
                                  </Button>
                                  <Link to={`/workflow-canvas/${workflow.id}`}>
                                    <Button
                                      size="sm"
                                      className="h-7 text-xs px-2"
                                    >
                                      <Pencil className="mr-1 h-3 w-3" />
                                      Edit
                                    </Button>
                                  </Link>
                                </div>
                              </CardFooter>
                            </Card>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </TabsContent>
              </Tabs>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
