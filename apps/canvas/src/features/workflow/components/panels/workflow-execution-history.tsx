import { useState, useEffect, useMemo } from "react";
import { Button } from "@/design-system/ui/button";
import { Badge } from "@/design-system/ui/badge";
import { ScrollArea } from "@/design-system/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/design-system/ui/pagination";
import { Edge, Node, MarkerType } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Clock,
  MessageSquare,
  Filter,
  RefreshCw,
  Copy,
  Trash,
  Maximize2,
  Minimize2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  getNodeIcon,
  inferNodeIconKey,
} from "@features/workflow/lib/node-icons";
import SidebarLayout from "@features/workflow/components/layouts/sidebar-layout";
import WorkflowFlow from "@features/workflow/components/canvas/workflow-flow";
import NodeInspector from "@features/workflow/components/panels/node-inspector";

// Remove default ReactFlow node container styling
const defaultNodeStyle = {
  background: "none",
  border: "none",
  padding: 0,
  borderRadius: 0,
  width: "auto",
  boxShadow: "none",
};

export interface WorkflowNode {
  id: string;
  type: string;
  name: string;
  position: { x: number; y: number };
  iconKey?: string;
  status?: "success" | "error" | "running" | "idle" | "warning";
  details?: {
    method?: string;
    url?: string;
    message?: string;
    items?: number;
    description?: string;
  };
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
}

export interface WorkflowExecution {
  id: string;
  runId: string;
  status: "success" | "failed" | "partial" | "running";
  startTime: string;
  endTime?: string;
  duration: number;
  issues: number;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  logs: {
    timestamp: string;
    level: "INFO" | "DEBUG" | "ERROR" | "WARNING";
    message: string;
  }[];
  metadata?: {
    graphToCanvas?: Record<string, string>;
  };
}

interface WorkflowExecutionHistoryProps {
  executions: WorkflowExecution[];
  onViewDetails?: (execution: WorkflowExecution) => void;
  onRefresh?: () => void;
  onCopyToEditor?: (execution: WorkflowExecution) => void;
  onDelete?: (execution: WorkflowExecution) => void;
  className?: string;
  showList?: boolean;
  defaultSelectedExecution?: WorkflowExecution;
}

const determineReactFlowNodeType = (
  type: string | undefined,
): "default" | "chatTrigger" | "startEnd" => {
  if (type === "chatTrigger") {
    return "chatTrigger";
  }
  if (type === "start" || type === "end") {
    return "startEnd";
  }
  return "default";
};

const normaliseNodeStatus = (
  status: WorkflowNode["status"],
): "idle" | "running" | "success" | "error" => {
  switch (status) {
    case "running":
      return "running";
    case "success":
      return "success";
    case "error":
      return "error";
    case "warning":
      return "running";
    default:
      return "idle";
  }
};

const parseChatTriggerDescription = (
  details: WorkflowNode["details"],
): string | undefined => {
  if (!details) {
    return undefined;
  }
  if (typeof details.message === "string" && details.message.trim()) {
    return details.message;
  }
  if (typeof details.description === "string" && details.description.trim()) {
    return details.description;
  }
  return undefined;
};

export default function WorkflowExecutionHistory({
  executions = [],
  onViewDetails,
  onRefresh,
  onCopyToEditor,
  onDelete,
  className,
  showList = true,
  defaultSelectedExecution,
}: WorkflowExecutionHistoryProps) {
  const [selectedExecution, setSelectedExecution] =
    useState<WorkflowExecution | null>(
      defaultSelectedExecution ||
        (executions.length > 0 ? executions[0] : null),
    );
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(300);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const totalExecutions = executions.length;

  // Get selected node for inspector
  const selectedNode = useMemo(() => {
    if (!selectedNodeId || !selectedExecution) {
      return null;
    }
    const node = selectedExecution.nodes.find((n) => n.id === selectedNodeId);
    if (!node) {
      return null;
    }

    // Transform WorkflowNode to the format expected by NodeInspector
    return {
      id: node.id,
      type: node.type || "default",
      data: {
        type: node.type || "default",
        label: node.name,
        status: normaliseNodeStatus(node.status),
        iconKey: node.iconKey,
        details: node.details,
        // Include any other fields that might be useful
        ...(node.details || {}),
      },
    };
  }, [selectedNodeId, selectedExecution]);
  const pageCount =
    totalExecutions === 0 ? 0 : Math.ceil(totalExecutions / pageSize);
  const startOffset = page * pageSize;
  const endOffset = Math.min(totalExecutions, startOffset + pageSize);
  const currentPageExecutions = useMemo(() => {
    const startIndex = page * pageSize;
    return executions.slice(startIndex, startIndex + pageSize);
  }, [executions, page, pageSize]);
  const pageSizeOptions = [10, 20, 50];
  const isFirstPage = page === 0 || pageCount === 0;
  const isLastPage = pageCount === 0 || page === pageCount - 1;

  const handleSelectExecution = (execution: WorkflowExecution) => {
    setSelectedExecution(execution);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();

    if (date.toDateString() === now.toDateString()) {
      return `Today, ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    } else if (
      date.toDateString() ===
      new Date(now.setDate(now.getDate() - 1)).toDateString()
    ) {
      return `Yesterday, ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    } else {
      return (
        date.toLocaleDateString([], {
          month: "short",
          day: "numeric",
          year: "numeric",
        }) +
        `, ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
      );
    }
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    const seconds = ms / 1000;
    return `${seconds.toFixed(1)}s`;
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status.toLowerCase()) {
      case "success":
        return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400";
      case "failed":
        return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400";
      case "partial":
        return "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400";
      case "running":
        return "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400";
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400";
    }
  };

  // Convert workflow nodes to ReactFlow nodes
  const getReactFlowNodes = (): Node[] => {
    if (!selectedExecution) return [];

    return selectedExecution.nodes.map((node) => {
      const semanticType =
        typeof node.type === "string" ? node.type : "default";
      const reactFlowType = determineReactFlowNodeType(semanticType);
      const status = normaliseNodeStatus(node.status);

      if (reactFlowType === "startEnd") {
        return {
          id: node.id,
          type: reactFlowType,
          position: node.position,
          style: defaultNodeStyle,
          width: 64,
          height: 64,
          data: {
            label: node.name,
            type: semanticType === "end" ? "end" : "start",
          },
        } as Node;
      }

      if (reactFlowType === "chatTrigger") {
        return {
          id: node.id,
          type: reactFlowType,
          position: node.position,
          style: defaultNodeStyle,
          width: 180,
          height: 120,
          data: {
            label: node.name,
            type: "chatTrigger",
            description: parseChatTriggerDescription(node.details),
            status,
          },
        } as Node;
      }

      const iconKey =
        node.iconKey ??
        inferNodeIconKey({
          iconKey: node.iconKey,
          label: node.name,
          type: semanticType,
        });

      return {
        id: node.id,
        type: reactFlowType,
        position: node.position,
        style: defaultNodeStyle,
        width: 64,
        height: 64,
        data: {
          label: node.name,
          status,
          type: semanticType,
          iconKey,
          icon: iconKey ? getNodeIcon(iconKey) : undefined,
        },
      } as Node;
    });
  };

  // Convert workflow edges to ReactFlow edges
  const getReactFlowEdges = (): Edge[] => {
    if (!selectedExecution) return [];

    return selectedExecution.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: "smoothstep",
      animated: selectedExecution.status === "running",
      style: { stroke: "#99a1b3", strokeWidth: 2 },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 20,
        height: 20,
      },
    }));
  };

  useEffect(() => {
    setSelectedExecution((current) => {
      if (executions.length === 0) {
        return null;
      }

      if (current) {
        const currentMatch = executions.find(
          (execution) => execution.id === current.id,
        );

        if (currentMatch) {
          return currentMatch;
        }
      }

      if (defaultSelectedExecution) {
        const defaultMatch = executions.find(
          (execution) => execution.id === defaultSelectedExecution.id,
        );

        if (defaultMatch) {
          return defaultMatch;
        }
      }

      return executions[0];
    });
  }, [executions, defaultSelectedExecution]);

  useEffect(() => {
    if (pageCount === 0) {
      if (page !== 0) {
        setPage(0);
      }
      return;
    }

    if (page > pageCount - 1) {
      setPage(pageCount - 1);
    }
  }, [page, pageCount]);

  // Sidebar content (executions list)
  const sidebarContent = (
    <div className="flex h-full flex-col">
      <div className="space-y-2 border-b border-border p-2">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold">Executions</h2>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              onClick={onRefresh}
              title="Refresh"
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="icon" title="Filter">
              <Filter className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {totalExecutions === 1
              ? "1 execution"
              : `${totalExecutions} executions`}
          </span>
          <div className="flex items-center gap-2">
            <span>Rows</span>
            <Select
              value={String(pageSize)}
              onValueChange={(value) => {
                const nextPageSize = Number(value);
                setPage(0);
                setPageSize(nextPageSize);
              }}
            >
              <SelectTrigger className="h-8 w-[80px]">
                <SelectValue aria-label="Rows per page" />
              </SelectTrigger>
              <SelectContent>
                {pageSizeOptions.map((option) => (
                  <SelectItem key={option} value={String(option)}>
                    {option}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-2">
          {totalExecutions === 0 ? (
            <div className="py-8 text-center text-muted-foreground">
              No executions found
            </div>
          ) : (
            currentPageExecutions.map((execution) => (
              <div
                key={execution.id}
                className={cn(
                  "mb-2 cursor-pointer rounded-lg border p-4 transition-colors",
                  selectedExecution?.id === execution.id
                    ? "border-primary bg-primary/5"
                    : "border-border hover:border-primary/50",
                )}
                onClick={() => handleSelectExecution(execution)}
              >
                <div className="mb-2 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge
                      className={cn(getStatusBadgeClass(execution.status))}
                    >
                      {execution.status.charAt(0).toUpperCase() +
                        execution.status.slice(1)}
                    </Badge>
                    <span className="font-medium">Run #{execution.runId}</span>
                  </div>
                  <span className="text-sm text-muted-foreground">
                    {formatDate(execution.startTime)}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-1">
                      <Clock className="h-4 w-4 text-muted-foreground" />

                      <span>{formatDuration(execution.duration)}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <MessageSquare className="h-4 w-4 text-muted-foreground" />

                      <span>
                        {execution.issues}{" "}
                        {execution.issues === 1 ? "issue" : "issues"}
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2"
                      onClick={(e) => {
                        e.stopPropagation();
                        onViewDetails?.(execution);
                      }}
                    >
                      View Details
                    </Button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </ScrollArea>
      <div className="flex flex-col gap-2 border-t border-border p-2 text-sm md:flex-row md:items-center md:justify-between">
        <span className="text-xs text-muted-foreground md:text-sm">
          {totalExecutions === 0
            ? "No executions to display"
            : `Showing ${startOffset + 1}-${endOffset} of ${totalExecutions}`}
        </span>
        <Pagination className="mx-0 justify-center md:justify-end">
          <PaginationContent>
            <PaginationItem>
              <PaginationPrevious
                href="#"
                onClick={(event) => {
                  event.preventDefault();
                  if (!isFirstPage) {
                    setPage((prev) => Math.max(prev - 1, 0));
                  }
                }}
                className={cn(isFirstPage && "pointer-events-none opacity-50")}
              />
            </PaginationItem>
            <PaginationItem>
              <PaginationLink
                href="#"
                isActive
                onClick={(event) => event.preventDefault()}
                className="px-3"
              >
                {`Page ${pageCount === 0 ? 0 : page + 1} of ${Math.max(
                  pageCount,
                  1,
                )}`}
              </PaginationLink>
            </PaginationItem>
            <PaginationItem>
              <PaginationNext
                href="#"
                onClick={(event) => {
                  event.preventDefault();
                  if (!isLastPage) {
                    setPage((prev) => Math.min(prev + 1, pageCount - 1));
                  }
                }}
                className={cn(isLastPage && "pointer-events-none opacity-50")}
              />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      </div>
    </div>
  );

  // Main content (execution details)
  const mainContent = selectedExecution ? (
    <>
      <div className="p-2 border-b border-border flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Badge
              className={cn(getStatusBadgeClass(selectedExecution.status))}
            >
              {selectedExecution.status.charAt(0).toUpperCase() +
                selectedExecution.status.slice(1)}
            </Badge>
            Run #{selectedExecution.runId}
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onCopyToEditor?.(selectedExecution)}
            title="Copy to editor"
          >
            <Copy className="h-4 w-4 mr-2" />
            Copy to editor
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={() => onDelete?.(selectedExecution)}
            title="Delete execution"
          >
            <Trash className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex-1 flex flex-col overflow-hidden p-2">
        <div
          className={cn(
            "relative border border-border rounded-lg overflow-hidden bg-muted/20 flex-1",
            isFullscreen && "fixed inset-0 z-50 p-4 bg-background",
          )}
        >
          <WorkflowFlow
            nodes={getReactFlowNodes()}
            edges={getReactFlowEdges()}
            fitView
            editable={false}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={true}
            zoomOnDoubleClick={false}
            showMiniMap={true}
            onNodeDoubleClick={(_event: React.MouseEvent, node: Node) => {
              // Ignore double-clicks on Start and End nodes
              if (node.type === "startEnd") {
                return;
              }
              setSelectedNodeId(node.id);
            }}
          >
            {/* Fullscreen button */}
            <div className="absolute top-4 right-4 z-10">
              <Button
                variant="outline"
                size="icon"
                onClick={() => setIsFullscreen(!isFullscreen)}
                title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
              >
                {isFullscreen ? (
                  <Minimize2 className="h-4 w-4" />
                ) : (
                  <Maximize2 className="h-4 w-4" />
                )}
              </Button>
            </div>
          </WorkflowFlow>
        </div>
      </div>
    </>
  ) : (
    <div className="flex items-center justify-center h-full text-muted-foreground">
      Select an execution to view details
    </div>
  );

  // Render with or without sidebar
  const content = (
    <>
      {showList ? (
        <SidebarLayout
          sidebar={sidebarContent}
          sidebarWidth={sidebarWidth}
          onWidthChange={setSidebarWidth}
          resizable
          minWidth={200}
          maxWidth={500}
          showCollapseButton={false}
        >
          <div className="flex flex-col h-full">{mainContent}</div>
        </SidebarLayout>
      ) : (
        mainContent
      )}

      {/* Node Inspector */}
      {selectedNode && (
        <NodeInspector
          node={selectedNode}
          onClose={() => setSelectedNodeId(null)}
          className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-50"
        />
      )}
    </>
  );

  if (!showList) {
    return (
      <div className={cn("h-full w-full flex flex-col", className)}>
        {content}
      </div>
    );
  }

  return <div className={cn("h-full w-full", className)}>{content}</div>;
}
