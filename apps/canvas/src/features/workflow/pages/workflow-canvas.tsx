import React, {
  useState,
  useCallback,
  useRef,
  useEffect,
  useLayoutEffect,
} from "react";
import { useParams } from "react-router-dom";
import type {
  Connection,
  Edge,
  EdgeChange,
  Node,
  NodeChange,
  ReactFlowInstance,
} from "@xyflow/react";
import {
  ReactFlow,
  Background,
  Controls,
  Panel,
  addEdge,
  useNodesState,
  useEdgesState,
  MarkerType,
  ConnectionLineType,
  MiniMap,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { Button } from "@/design-system/ui/button";
import { Tabs, TabsContent } from "@/design-system/ui/tabs";
import { Separator } from "@/design-system/ui/separator";

import TopNavigation from "@features/shared/components/top-navigation";
import SidebarPanel from "@features/workflow/components/panels/sidebar-panel";
import WorkflowNode from "@features/workflow/components/nodes/workflow-node";
import WorkflowControls from "@features/workflow/components/canvas/workflow-controls";
import NodeInspector from "@features/workflow/components/panels/node-inspector";
import ChatTriggerNode from "@features/workflow/components/nodes/chat-trigger-node";
import ChatInterface from "@features/shared/components/chat-interface";
import type { Attachment } from "@features/shared/components/chat-input";
import WorkflowExecutionHistory, {
  type WorkflowExecution as HistoryWorkflowExecution,
} from "@features/workflow/components/panels/workflow-execution-history";
import WorkflowTabs from "@features/workflow/components/panels/workflow-tabs";
import StartEndNode from "@features/workflow/components/nodes/start-end-node";
import { SAMPLE_WORKFLOWS } from "@features/workflow/data/workflow-data";
import { toast } from "@/hooks/use-toast";

// Define custom node types
const nodeTypes = {
  default: WorkflowNode,
  chatTrigger: ChatTriggerNode,
  startEnd: StartEndNode,
};

// Add default style to remove ReactFlow node container
const defaultNodeStyle = {
  background: "none",
  border: "none",
  padding: 0,
  borderRadius: 0,
  width: "auto",
  boxShadow: "none",
};

const generateNodeId = () => {
  if (
    typeof globalThis.crypto !== "undefined" &&
    "randomUUID" in globalThis.crypto &&
    typeof globalThis.crypto.randomUUID === "function"
  ) {
    return `node-${globalThis.crypto.randomUUID()}`;
  }

  const timestamp = Date.now().toString(36);
  const randomSuffix = Math.random().toString(36).slice(2, 8);
  return `node-${timestamp}-${randomSuffix}`;
};

interface NodeData {
  type: string;
  label: string;
  description?: string;
  status: "idle" | "running" | "success" | "error" | "warning";
  icon?: React.ReactNode;
  onOpenChat?: () => void;
  isDisabled?: boolean;
  [key: string]: unknown;
}

type WorkflowNode = Node<NodeData>;
type WorkflowEdge = Edge<Record<string, unknown>>;

interface WorkflowSnapshot {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

interface WorkflowCanvasProps {
  initialNodes?: WorkflowNode[];
  initialEdges?: WorkflowEdge[];
}

const HISTORY_LIMIT = 50;

const cloneNode = (node: WorkflowNode): WorkflowNode => ({
  ...node,
  position: node.position ? { ...node.position } : node.position,
  data: node.data ? { ...node.data } : node.data,
});

const cloneEdge = (edge: WorkflowEdge): WorkflowEdge => ({
  ...edge,
  data: edge.data ? { ...edge.data } : edge.data,
});

// Update the WorkflowExecution interface to match the component's expectations
type WorkflowExecutionStatus = "running" | "success" | "failed" | "partial";
type NodeStatus = "idle" | "running" | "success" | "error" | "warning";

interface WorkflowExecutionNode {
  id: string;
  type: string;
  name: string;
  position: { x: number; y: number };
  status: NodeStatus;
  details?: Record<string, unknown>;
}

interface WorkflowExecution {
  id: string;
  runId: string;
  status: WorkflowExecutionStatus;
  startTime: string;
  endTime?: string;
  duration: number;
  issues: number;
  nodes: WorkflowExecutionNode[];
  edges: WorkflowEdge[];
  logs: {
    timestamp: string;
    level: "INFO" | "DEBUG" | "ERROR" | "WARNING";
    message: string;
  }[];
}

interface SidebarNodeDefinition {
  id?: string;
  type?: string;
  name?: string;
  description?: string;
  icon?: React.ReactNode;
  data?: Record<string, unknown>;
}

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === "object" && value !== null;
};

const determineNodeType = (nodeId?: string) => {
  if (nodeId?.includes("chat-trigger")) {
    return "chatTrigger" as const;
  }
  if (nodeId === "start-node" || nodeId === "end-node") {
    return "startEnd" as const;
  }
  return "default" as const;
};

const validateWorkflowData = (data: unknown) => {
  if (!isRecord(data)) {
    throw new Error("Invalid workflow file structure.");
  }

  const { nodes, edges } = data;

  if (!Array.isArray(nodes)) {
    throw new Error("Invalid nodes array in workflow file.");
  }

  nodes.forEach((node, index) => {
    if (!isRecord(node)) {
      throw new Error(`Invalid node at index ${index}.`);
    }
    if (!isRecord(node.position)) {
      throw new Error(`Node ${node.id ?? index} is missing position data.`);
    }
    const { x, y } = node.position as Record<string, unknown>;
    if (typeof x !== "number" || typeof y !== "number") {
      throw new Error(`Node ${node.id ?? index} has invalid coordinates.`);
    }
  });

  if (!Array.isArray(edges)) {
    throw new Error("Invalid edges array in workflow file.");
  }

  edges.forEach((edge, index) => {
    if (!isRecord(edge)) {
      throw new Error(`Invalid edge at index ${index}.`);
    }
    if (typeof edge.source !== "string" || typeof edge.target !== "string") {
      throw new Error(`Edge ${edge.id ?? index} has invalid connections.`);
    }
  });
};

export default function WorkflowCanvas({
  initialNodes = [],
  initialEdges = [],
}: WorkflowCanvasProps) {
  const { workflowId } = useParams<{ workflowId?: string }>();

  // Initialize with empty arrays instead of sample workflow
  const [nodes, setNodesState, onNodesChangeState] =
    useNodesState<WorkflowNode>(initialNodes);
  const [edges, setEdgesState, onEdgesChangeState] =
    useEdgesState<WorkflowEdge>(initialEdges);
  const [workflowName, setWorkflowName] = useState("New Workflow");

  // State for UI controls
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);
  const [selectedNode, setSelectedNode] = useState<WorkflowNode | null>(null);
  const [activeTab, setActiveTab] = useState("canvas");

  // Chat interface state
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [activeChatNodeId, setActiveChatNodeId] = useState<string | null>(null);
  const [chatTitle, setChatTitle] = useState("Chat");

  const undoStackRef = useRef<WorkflowSnapshot[]>([]);
  const redoStackRef = useRef<WorkflowSnapshot[]>([]);
  const isRestoringRef = useRef(false);
  const nodesRef = useRef<WorkflowNode[]>(nodes);
  const edgesRef = useRef<WorkflowEdge[]>(edges);

  // Refs
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const reactFlowInstance = useRef<ReactFlowInstance<
    WorkflowNode,
    WorkflowEdge
  > | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const createSnapshot = useCallback((): WorkflowSnapshot => ({
    nodes: nodesRef.current.map(cloneNode),
    edges: edgesRef.current.map(cloneEdge),
  }), []);

  const recordSnapshot = useCallback(
    (options?: { force?: boolean }) => {
      if (isRestoringRef.current && !options?.force) {
        return;
      }
      const snapshot = createSnapshot();
      undoStackRef.current = [...undoStackRef.current, snapshot].slice(
        -HISTORY_LIMIT,
      );
      redoStackRef.current = [];
      setCanUndo(undoStackRef.current.length > 0);
      setCanRedo(false);
    },
    [createSnapshot],
  );

  const applySnapshot = useCallback(
    (snapshot: WorkflowSnapshot, { resetHistory = false } = {}) => {
      isRestoringRef.current = true;
      setNodesState(snapshot.nodes);
      setEdgesState(snapshot.edges);
      if (resetHistory) {
        undoStackRef.current = [];
        redoStackRef.current = [];
        setCanUndo(false);
        setCanRedo(false);
      }
    },
    [setCanRedo, setCanUndo, setEdgesState, setNodesState],
  );

  useLayoutEffect(() => {
    if (isRestoringRef.current) {
      isRestoringRef.current = false;
    }
  }, [edges, nodes]);

  useEffect(() => {
    nodesRef.current = nodes;
  }, [nodes]);

  useEffect(() => {
    edgesRef.current = edges;
  }, [edges]);

  const setNodes = useCallback(
    (updater: React.SetStateAction<WorkflowNode[]>) => {
      if (!isRestoringRef.current) {
        recordSnapshot();
      }
      setNodesState((current) =>
        typeof updater === "function"
          ? (updater as (value: WorkflowNode[]) => WorkflowNode[])(current)
          : updater,
      );
    },
    [recordSnapshot, setNodesState],
  );

  const setEdges = useCallback(
    (updater: React.SetStateAction<WorkflowEdge[]>) => {
      if (!isRestoringRef.current) {
        recordSnapshot();
      }
      setEdgesState((current) =>
        typeof updater === "function"
          ? (updater as (value: WorkflowEdge[]) => WorkflowEdge[])(current)
          : updater,
      );
    },
    [recordSnapshot, setEdgesState],
  );

  const handleNodesChange = useCallback(
    (changes: NodeChange<WorkflowNode>[]) => {
      const shouldRecord = changes.some((change) => {
        if (change.type === "select") {
          return false;
        }
        if (change.type === "position" && change.dragging) {
          return false;
        }
        return true;
      });
      if (shouldRecord) {
        recordSnapshot();
      }
      onNodesChangeState(changes);
    },
    [onNodesChangeState, recordSnapshot],
  );

  const handleEdgesChange = useCallback(
    (changes: EdgeChange<WorkflowEdge>[]) => {
      if (changes.some((change) => change.type !== "select")) {
        recordSnapshot();
      }
      onEdgesChangeState(changes);
    },
    [onEdgesChangeState, recordSnapshot],
  );

  // Sample executions for the WorkflowExecutionHistory component
  const mockExecutions: WorkflowExecution[] = [
    {
      id: "1",
      runId: "842",
      status: "success",
      startTime: new Date().toISOString(),
      duration: 45200,
      issues: 0,
      nodes: [
        {
          id: "node-1",
          type: "webhook",
          name: "New Customer Webhook",
          position: { x: 100, y: 100 },
          status: "success",
        },
        {
          id: "node-2",
          type: "http",
          name: "Fetch Customer Details",
          position: { x: 400, y: 100 },
          status: "success",
          details: {
            method: "GET",
            url: "https://api.example.com/customers/123",
            items: 1,
          },
        },
        {
          id: "node-3",
          type: "function",
          name: "Format Customer Data",
          position: { x: 700, y: 100 },
          status: "success",
        },
        {
          id: "node-4",
          type: "api",
          name: "Create Account",
          position: { x: 400, y: 250 },
          status: "success",
        },
        {
          id: "node-5",
          type: "api",
          name: "Send Welcome Email",
          position: { x: 700, y: 250 },
          status: "success",
          details: {
            message: "Welcome to our platform!",
          },
        },
      ],
      edges: [
        { id: "edge-1", source: "node-1", target: "node-2", type: "default" },
        { id: "edge-2", source: "node-2", target: "node-3" },
        { id: "edge-3", source: "node-3", target: "node-4" },
        { id: "edge-4", source: "node-4", target: "node-5" },
      ],
      logs: [
        {
          timestamp: "10:23:15",
          level: "INFO",
          message: "Workflow execution started",
        },
        {
          timestamp: "10:23:16",
          level: "DEBUG",
          message: 'Executing node "New Customer Webhook"',
        },
        {
          timestamp: "10:23:17",
          level: "INFO",
          message: 'Node "New Customer Webhook" completed successfully',
        },
        {
          timestamp: "10:23:18",
          level: "DEBUG",
          message: 'Executing node "Fetch Customer Details"',
        },
        {
          timestamp: "10:23:20",
          level: "INFO",
          message: 'Node "Fetch Customer Details" completed successfully',
        },
        {
          timestamp: "10:23:21",
          level: "DEBUG",
          message: 'Executing node "Format Customer Data"',
        },
        {
          timestamp: "10:23:23",
          level: "INFO",
          message: 'Node "Format Customer Data" completed successfully',
        },
        {
          timestamp: "10:23:24",
          level: "DEBUG",
          message: 'Executing node "Create Account"',
        },
        {
          timestamp: "10:23:40",
          level: "INFO",
          message: 'Node "Create Account" completed successfully',
        },
        {
          timestamp: "10:23:41",
          level: "DEBUG",
          message: 'Executing node "Send Welcome Email"',
        },
        {
          timestamp: "10:23:45",
          level: "INFO",
          message: 'Node "Send Welcome Email" completed successfully',
        },
        {
          timestamp: "10:23:45",
          level: "INFO",
          message: "Workflow execution completed successfully",
        },
      ],
    },
    {
      id: "2",
      runId: "841",
      status: "failed",
      startTime: new Date(Date.now() - 86400000).toISOString(), // yesterday
      duration: 134700,
      issues: 3,
      nodes: [
        {
          id: "node-1",
          type: "webhook",
          name: "New Customer Webhook",
          position: { x: 100, y: 100 },
          status: "success",
        },
        {
          id: "node-2",
          type: "http",
          name: "Fetch Customer Details",
          position: { x: 400, y: 100 },
          status: "success",
          details: {
            method: "GET",
            url: "https://api.example.com/customers/456",
            items: 1,
          },
        },
        {
          id: "node-3",
          type: "function",
          name: "Format Customer Data",
          position: { x: 700, y: 100 },
          status: "success",
        },
        {
          id: "node-4",
          type: "api",
          name: "Create Account",
          position: { x: 400, y: 250 },
          status: "error",
          details: {
            message: "Email already exists",
          },
        },
        {
          id: "node-5",
          type: "api",
          name: "Send Welcome Email",
          position: { x: 700, y: 250 },
          status: "idle",
        },
      ],
      edges: [
        { id: "edge-1", source: "node-1", target: "node-2" },
        { id: "edge-2", source: "node-2", target: "node-3" },
        { id: "edge-3", source: "node-3", target: "node-4" },
        { id: "edge-4", source: "node-4", target: "node-5" },
      ],
      logs: [
        {
          timestamp: "15:45:10",
          level: "INFO",
          message: "Workflow execution started",
        },
        {
          timestamp: "15:45:11",
          level: "DEBUG",
          message: 'Executing node "New Customer Webhook"',
        },
        {
          timestamp: "15:45:12",
          level: "INFO",
          message: 'Node "New Customer Webhook" completed successfully',
        },
        {
          timestamp: "15:45:13",
          level: "DEBUG",
          message: 'Executing node "Fetch Customer Details"',
        },
        {
          timestamp: "15:45:15",
          level: "INFO",
          message: 'Node "Fetch Customer Details" completed successfully',
        },
        {
          timestamp: "15:45:16",
          level: "DEBUG",
          message: 'Executing node "Format Customer Data"',
        },
        {
          timestamp: "15:45:18",
          level: "INFO",
          message: 'Node "Format Customer Data" completed successfully',
        },
        {
          timestamp: "15:45:19",
          level: "DEBUG",
          message: 'Executing node "Create Account"',
        },
        {
          timestamp: "15:45:30",
          level: "ERROR",
          message: 'Error in node "Create Account": Email already exists',
        },
        {
          timestamp: "15:45:30",
          level: "INFO",
          message: "Workflow execution failed",
        },
      ],
    },
    {
      id: "3",
      runId: "840",
      status: "partial",
      startTime: new Date("2023-11-03T09:12:00").toISOString(),
      duration: 67300,
      issues: 1,
      nodes: [
        {
          id: "node-1",
          type: "webhook",
          name: "New Customer Webhook",
          position: { x: 100, y: 100 },
          status: "success",
        },
        {
          id: "node-2",
          type: "http",
          name: "Fetch Customer Details",
          position: { x: 400, y: 100 },
          status: "success",
        },
        {
          id: "node-3",
          type: "function",
          name: "Format Customer Data",
          position: { x: 700, y: 100 },
          status: "success",
        },
        {
          id: "node-4",
          type: "api",
          name: "Create Account",
          position: { x: 400, y: 250 },
          status: "success",
        },
        {
          id: "node-5",
          type: "api",
          name: "Send Welcome Email",
          position: { x: 700, y: 250 },
          status: "success",
        },
      ],
      edges: [
        { id: "edge-1", source: "node-1", target: "node-2" },
        { id: "edge-2", source: "node-2", target: "node-3" },
        { id: "edge-3", source: "node-3", target: "node-4" },
        { id: "edge-4", source: "node-4", target: "node-5" },
      ],
      logs: [
        {
          timestamp: "09:12:00",
          level: "INFO",
          message: "Workflow execution started",
        },
        {
          timestamp: "09:12:01",
          level: "DEBUG",
          message: 'Executing node "Daily Report Trigger"',
        },
        {
          timestamp: "09:12:02",
          level: "INFO",
          message: 'Node "Daily Report Trigger" completed successfully',
        },
        {
          timestamp: "09:12:03",
          level: "DEBUG",
          message: 'Executing node "Fetch Sales Data"',
        },
        {
          timestamp: "09:12:10",
          level: "INFO",
          message: 'Node "Fetch Sales Data" completed successfully',
        },
        {
          timestamp: "09:12:11",
          level: "DEBUG",
          message: 'Executing node "Generate Report"',
        },
        {
          timestamp: "09:12:30",
          level: "INFO",
          message: 'Node "Generate Report" completed successfully',
        },
        {
          timestamp: "09:12:31",
          level: "DEBUG",
          message: 'Executing node "Email Report"',
        },
        {
          timestamp: "09:12:40",
          level: "INFO",
          message: 'Node "Email Report" completed successfully',
        },
        {
          timestamp: "09:12:41",
          level: "DEBUG",
          message: 'Executing node "Slack Notification"',
        },
        {
          timestamp: "09:12:45",
          level: "WARNING",
          message:
            'Node "Slack Notification" completed with warnings: Channel not found',
        },
        {
          timestamp: "09:12:45",
          level: "INFO",
          message: "Workflow execution completed with warnings",
        },
      ],
    },
  ];

  const handleDuplicateSelectedNodes = useCallback(() => {
    const selectedNodes = nodes.filter((node) => node.selected);
    if (selectedNodes.length === 0) {
      toast({
        title: "No nodes selected",
        description: "Select at least one node to duplicate.",
        variant: "destructive",
      });
      return;
    }

    const idMap = new Map<string, string>();
    const duplicatedNodes = selectedNodes.map((node) => {
      const newId = generateNodeId();
      idMap.set(node.id, newId);
      const clonedNode = cloneNode(node);
      const baseLabel =
        typeof clonedNode.data?.label === "string"
          ? clonedNode.data.label
          : clonedNode.id;
      return {
        ...clonedNode,
        id: newId,
        position: {
          x: (clonedNode.position?.x ?? 0) + 40,
          y: (clonedNode.position?.y ?? 0) + 40,
        },
        selected: false,
        data: {
          ...clonedNode.data,
          label: `${baseLabel} Copy`,
        },
      } as WorkflowNode;
    });

    const selectedIds = new Set(selectedNodes.map((node) => node.id));
    const duplicatedEdges = edges
      .filter(
        (edge) =>
          selectedIds.has(edge.source) && selectedIds.has(edge.target),
      )
      .map((edge) => {
        const sourceId = idMap.get(edge.source);
        const targetId = idMap.get(edge.target);
        if (!sourceId || !targetId) {
          return null;
        }
        const clonedEdge = cloneEdge(edge);
        return {
          ...clonedEdge,
          id: `edge-${sourceId}-${targetId}-${Math.random()
            .toString(36)
            .slice(2, 8)}`,
          source: sourceId,
          target: targetId,
          selected: false,
        } as WorkflowEdge;
      })
      .filter(Boolean) as WorkflowEdge[];

    isRestoringRef.current = true;
    recordSnapshot({ force: true });
    try {
      setNodesState((current) => [...current, ...duplicatedNodes]);
      if (duplicatedEdges.length > 0) {
        setEdgesState((current) => [...current, ...duplicatedEdges]);
      }
    } catch (error) {
      isRestoringRef.current = false;
      throw error;
    }
    toast({
      title: "Nodes duplicated",
      description: `${duplicatedNodes.length} node${
        duplicatedNodes.length === 1 ? "" : "s"
      } copied with their connections.`,
    });
  }, [edges, nodes, recordSnapshot, setEdgesState, setNodesState]);

  const handleExportWorkflow = useCallback(() => {
    try {
      const snapshot = createSnapshot();
      const workflowData = {
        name: workflowName,
        nodes: snapshot.nodes,
        edges: snapshot.edges,
      };
      const serialized = JSON.stringify(workflowData, null, 2);
      const blob = new Blob([serialized], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${workflowName.replace(/\s+/g, "-").toLowerCase() || "workflow"}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      toast({
        title: "Workflow exported",
        description: "A JSON export has been downloaded.",
      });
    } catch (error) {
      toast({
        title: "Export failed",
        description:
          error instanceof Error ? error.message : "Unable to export workflow.",
        variant: "destructive",
      });
    }
  }, [createSnapshot, workflowName]);

  const handleImportWorkflow = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleWorkflowFileSelected = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) {
        return;
      }

      const reader = new FileReader();
      reader.onload = () => {
        try {
          const content = typeof reader.result === "string" ? reader.result : "";
          const parsed = JSON.parse(content);
          validateWorkflowData(parsed);

          const importedNodes = (parsed.nodes as WorkflowNode[]).map((node) => ({
            ...cloneNode(node),
            id: node.id ?? generateNodeId(),
            selected: false,
          }));
          const importedEdges = (parsed.edges as WorkflowEdge[]).map((edge) => ({
            ...cloneEdge(edge),
            id:
              edge.id ??
              `edge-${Math.random().toString(36).slice(2, 8)}-${Math.random()
                .toString(36)
                .slice(2, 8)}`,
            selected: false,
          }));

          isRestoringRef.current = true;
          recordSnapshot({ force: true });
          try {
            setNodesState(importedNodes);
            setEdgesState(importedEdges);
            if (
              typeof parsed.name === "string" &&
              parsed.name.trim().length > 0
            ) {
              setWorkflowName(parsed.name);
            }
          } catch (error) {
            isRestoringRef.current = false;
            throw error;
          }

          toast({
            title: "Workflow imported",
            description: `Loaded ${importedNodes.length} node${
              importedNodes.length === 1 ? "" : "s"
            } from file.`,
          });
        } catch (error) {
          toast({
            title: "Import failed",
            description:
              error instanceof Error ? error.message : "Invalid workflow file.",
            variant: "destructive",
          });
        } finally {
          event.target.value = "";
        }
      };
      reader.onerror = () => {
        toast({
          title: "Import failed",
          description: "Unable to read the selected file.",
          variant: "destructive",
        });
        event.target.value = "";
      };
      reader.readAsText(file);
    },
    [recordSnapshot, setEdgesState, setNodesState, setWorkflowName],
  );

  // Handle new connections between nodes
  const onConnect = useCallback(
    (params: Connection) => {
      const edgeId = `edge-${params.source}-${params.target}`;
      const connectionExists = edges.some(
        (edge) =>
          edge.source === params.source && edge.target === params.target,
      );

      if (!connectionExists) {
        setEdges((eds) =>
          addEdge(
            {
              ...params,
              id: edgeId,
              animated: false,
              type: "smoothstep",
              markerEnd: {
                type: MarkerType.ArrowClosed,
                width: 20,
                height: 20,
              },
              style: { stroke: "#99a1b3", strokeWidth: 2 },
            },
            eds,
          ),
        );
      }
    },
    [edges, setEdges],
  );

  // Handle node selection
  const onNodeClick = useCallback((event: React.MouseEvent) => {
    if (event.detail === 1) {
      // No-op for single clicks; double clicks handled separately
    }
  }, []);

  // Handle node double click for inspection
  const onNodeDoubleClick = useCallback(
    (_: React.MouseEvent, node: WorkflowNode) => {
      setSelectedNode(node);
    },
    [],
  );

  // Handle opening chat for a specific node
  const handleOpenChat = useCallback(
    (nodeId: string) => {
      const chatNode = nodes.find((node) => node.id === nodeId);
      if (chatNode) {
        setChatTitle(chatNode.data.label || "Chat");
        setActiveChatNodeId(nodeId);
        setIsChatOpen(true);
      }
    },
    [nodes],
  );

  // Handle drag over for dropping new nodes
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  // Handle drop for creating new nodes
  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      if (!reactFlowWrapper.current || !reactFlowInstance.current) return;

      const reactFlowBounds = reactFlowWrapper.current.getBoundingClientRect();
      const nodeData = event.dataTransfer.getData("application/reactflow");

      if (!nodeData) return;

      try {
        const node = JSON.parse(nodeData) as SidebarNodeDefinition;

        // Get the position where the node was dropped
        const position = reactFlowInstance.current.project({
          x: event.clientX - reactFlowBounds.left,
          y: event.clientY - reactFlowBounds.top,
        });

        const nodeType = determineNodeType(node.id);

        // Create a new node
        const nodeId = generateNodeId();

        const newNode: WorkflowNode = {
          id: nodeId,
          type: nodeType,
          position,
          style: defaultNodeStyle,
          data: {
            ...node,
            label: node.name || "New Node",
            description: node.description || "",
            type:
              nodeType === "startEnd"
                ? node.id === "start-node"
                  ? "start"
                  : "end"
                : node.id?.split("-")[0] || "default",
            status: "idle" as NodeStatus,
            icon: node.icon,
            onOpenChat:
              nodeType === "chatTrigger"
                ? () => handleOpenChat(nodeId)
                : undefined,
          },
          draggable: true,
        };

        // Add the new node to the canvas
        setNodes((nds) => nds.concat(newNode));
      } catch (error) {
        console.error("Error adding new node:", error);
      }
    },
    [handleOpenChat, setNodes],
  );

  // Handle adding a node by clicking
  const handleAddNode = useCallback(
    (node: SidebarNodeDefinition) => {
      if (!reactFlowInstance.current) return;

      const nodeType = determineNodeType(node.id);

      // Calculate a position for the new node
      const position = {
        x: Math.random() * 300 + 100,
        y: Math.random() * 300 + 100,
      };

      // Create a new node with explicit NodeData type
      const nodeId = generateNodeId();

      const newNode: Node<NodeData> = {
        id: nodeId,
        type: nodeType,
        position,
        style: defaultNodeStyle,
        data: {
          type:
            nodeType === "startEnd"
              ? node.id === "start-node"
                ? "start"
                : "end"
              : node.type || "default",
          label: node.name || "New Node",
          description: node.description || "",
          status: "idle" as NodeStatus,
          icon: node.icon,
          onOpenChat:
            nodeType === "chatTrigger"
              ? () => handleOpenChat(nodeId)
              : undefined,
        },
        draggable: true,
      };

      // Add the new node to the canvas
      setNodes((nds) => [...nds, newNode]);
    },
    [handleOpenChat, setNodes],
  );

  // Handle chat message sending
  const handleSendChatMessage = (
    message: string,
    attachments: Attachment[],
  ) => {
    if (!activeChatNodeId) {
      toast({
        title: "Select a chat-enabled node",
        description: "Open a node chat to send messages.",
      });
      return;
    }

    const activeNode = nodes.find((node) => node.id === activeChatNodeId);
    const attachmentSummary =
      attachments.length === 0
        ? ""
        : attachments.length === 1
          ? " with 1 attachment"
          : ` with ${attachments.length} attachments`;

    toast({
      title: `Message sent to ${activeNode?.data?.label ?? "workflow"}`,
      description: `"${message}"${attachmentSummary}`,
    });

    // Here you would typically process the message and trigger the workflow
    // For now, we'll just update the node status to simulate activity
    setNodes((nds) =>
      nds.map((n) => {
        if (n.id === activeChatNodeId) {
          return {
            ...n,
            data: {
              ...n.data,
              status: "running" as NodeStatus,
            },
          };
        }
        return n;
      }),
    );

    // Simulate workflow execution
    setTimeout(() => {
      setNodes((nds) =>
        nds.map((n) => {
          if (n.id === activeChatNodeId) {
            return {
              ...n,
              data: {
                ...n.data,
                status: "success" as NodeStatus,
              },
            };
          }
          return n;
        }),
      );
    }, 2000);
  };

  // Handle workflow execution
  const handleRunWorkflow = useCallback(() => {
    setIsRunning(true);

    // Simulate workflow execution by updating node statuses
    const nodeUpdates = [...nodes];
    let delay = 0;

    // Update nodes sequentially to simulate execution flow
    nodeUpdates.forEach((node) => {
      setTimeout(() => {
        setNodes((nds) =>
          nds.map((n) => {
            if (n.id === node.id) {
              return {
                ...n,
                data: {
                  ...n.data,
                  status: "running" as NodeStatus,
                },
              };
            }
            return n;
          }),
        );

        // After a delay, set the node to success
        setTimeout(() => {
          setNodes((nds) =>
            nds.map((n) => {
              if (n.id === node.id) {
                return {
                  ...n,
                  data: {
                    ...n.data,
                    status:
                      Math.random() > 0.9
                        ? ("error" as NodeStatus)
                        : ("success" as NodeStatus), // 10% chance of error
                  },
                };
              }
              return n;
            }),
          );

          // If this is the last node, set isRunning to false
          if (node.id === nodeUpdates[nodeUpdates.length - 1].id) {
            setIsRunning(false);
          }
        }, 1500);
      }, delay);

      delay += 1000; // Stagger the execution
    });
  }, [nodes, setNodes]);

  // Handle workflow pause
  const handlePauseWorkflow = useCallback(() => {
    setIsRunning(false);

    // Reset all running nodes to idle
    setNodes((nds) =>
      nds.map((n) => {
        if (n.data.status === "running") {
          return {
            ...n,
            data: {
              ...n.data,
              status: "idle" as NodeStatus,
            },
          };
        }
        return n;
      }),
    );
  }, [setNodes]);

  const handleUndo = useCallback(() => {
    const previousSnapshot = undoStackRef.current.pop();
    if (!previousSnapshot) {
      return;
    }
    const currentSnapshot = createSnapshot();
    redoStackRef.current = [...redoStackRef.current, currentSnapshot].slice(
      -HISTORY_LIMIT,
    );
    applySnapshot(previousSnapshot);
    setCanUndo(undoStackRef.current.length > 0);
    setCanRedo(true);
  }, [applySnapshot, createSnapshot]);

  const handleRedo = useCallback(() => {
    const nextSnapshot = redoStackRef.current.pop();
    if (!nextSnapshot) {
      return;
    }
    const currentSnapshot = createSnapshot();
    undoStackRef.current = [...undoStackRef.current, currentSnapshot].slice(
      -HISTORY_LIMIT,
    );
    applySnapshot(nextSnapshot);
    setCanRedo(redoStackRef.current.length > 0);
    setCanUndo(true);
  }, [applySnapshot, createSnapshot]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey)) {
        return;
      }

      const key = event.key.toLowerCase();

      if (key === "z") {
        event.preventDefault();
        if (event.shiftKey) {
          handleRedo();
        } else {
          handleUndo();
        }
        return;
      }

      if (key === "y") {
        event.preventDefault();
        handleRedo();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleRedo, handleUndo]);

  // Handle node inspector close
  const handleCloseNodeInspector = useCallback(() => {
    setSelectedNode(null);
  }, []);

  // Handle node update from inspector
  const handleNodeUpdate = useCallback(
    (nodeId: string, data: Partial<NodeData>) => {
      setNodes((nds) =>
        nds.map((n) => {
          if (n.id === nodeId) {
            const node = n as Node<NodeData>;
            return {
              ...node,
              data: {
                ...node.data,
                ...data,
                status:
                  data.status || node.data.status || ("idle" as NodeStatus),
              },
            };
          }
          return n;
        }),
      );
      setSelectedNode(null);
    },
    [setNodes],
  );

  // Handle execution selection
  const handleViewExecutionDetails = useCallback(
    (execution: HistoryWorkflowExecution) => {
      const mappedNodes = execution.nodes.map(
        (node) =>
          ({
            id: node.id,
            type: node.type || "default",
            position: node.position,
            data: {
              type: node.type || "default",
              label: node.name,
              status: node.status || ("idle" as const),
              details: node.details,
            } as NodeData,
            draggable: true,
          }) as Node<NodeData>,
      );
      setNodes(mappedNodes);
    },
    [setNodes],
  );

  // Load workflow data when workflowId changes
  useEffect(() => {
    if (workflowId) {
      const workflow = SAMPLE_WORKFLOWS.find((w) => w.id === workflowId);
      if (workflow) {
        setWorkflowName(workflow.name);

        // Convert workflow nodes to ReactFlow nodes
        const flowNodes = workflow.nodes.map((node) => ({
          id: node.id,
          type:
            node.type === "trigger" ||
            node.type === "api" ||
            node.type === "function" ||
            node.type === "data" ||
            node.type === "ai"
              ? "default"
              : node.type,
          position: node.position,
          style: defaultNodeStyle,
          data: {
            type: node.type,
            label: node.data.label,
            description: node.data.description,
            status: (node.data.status || "idle") as NodeStatus,
            isDisabled: node.data.isDisabled,
          } as NodeData,
          draggable: true,
        }));

        // Convert workflow edges to ReactFlow edges
        const flowEdges = workflow.edges.map((edge) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          sourceHandle: edge.sourceHandle,
          targetHandle: edge.targetHandle,
          label: edge.label,
          type: edge.type || "smoothstep",
          animated: edge.animated || false,
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 20,
            height: 20,
          },
          style: edge.style || { stroke: "#99a1b3", strokeWidth: 2 },
        }));

        applySnapshot({ nodes: flowNodes, edges: flowEdges }, { resetHistory: true });
      }
    }
  }, [applySnapshot, workflowId]);

  // Fit view on initial render
  useEffect(() => {
    setTimeout(() => {
      if (reactFlowInstance.current) {
        reactFlowInstance.current.fitView({ padding: 0.2 });
      }
    }, 100);
  }, [nodes]);

  // User and AI info for chat
  const user = {
    id: "user-1",
    name: "Avery Chen",
    avatar: "https://avatar.vercel.sh/avery",
  };

  const ai = {
    id: "ai-1",
    name: "Orcheo Canvas Assistant",
    avatar: "https://avatar.vercel.sh/orcheo-canvas",
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <TopNavigation
        currentWorkflow={{
          name: workflowName,
          path: ["Projects", "Workflows", workflowName],
        }}
      />

      <WorkflowTabs
        activeTab={activeTab}
        onTabChange={setActiveTab}
        executionCount={3}
      />

      <div className="flex-1 flex flex-col min-h-0">
        <Tabs
          value={activeTab}
          onValueChange={setActiveTab}
          className="w-full flex flex-col flex-1 min-h-0"
        >
          <TabsContent
            value="canvas"
            className="flex-1 m-0 p-0 overflow-hidden min-h-0"
          >
            <div className="flex h-full min-h-0">
              <SidebarPanel
                isCollapsed={sidebarCollapsed}
                onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
                onAddNode={handleAddNode}
              />

              <div
                ref={reactFlowWrapper}
                className="flex-1 h-full min-h-0"
                onDragOver={onDragOver}
                onDrop={onDrop}
              >
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  onNodesChange={handleNodesChange}
                  onEdgesChange={handleEdgesChange}
                  onConnect={onConnect}
                  onNodeClick={onNodeClick}
                  onNodeDoubleClick={onNodeDoubleClick}
                  onInit={(instance) => {
                    reactFlowInstance.current = instance;
                  }}
                  nodeTypes={nodeTypes}
                  fitView
                  snapToGrid
                  snapGrid={[15, 15]}
                  defaultEdgeOptions={{
                    style: { stroke: "#99a1b3", strokeWidth: 2 },
                    type: "smoothstep",
                    markerEnd: {
                      type: MarkerType.ArrowClosed,
                    },
                  }}
                  connectionLineType={ConnectionLineType.SmoothStep}
                  connectionLineStyle={{ stroke: "#99a1b3", strokeWidth: 2 }}
                  proOptions={{ hideAttribution: true }}
                  className="h-full"
                >
                  <Background />

                  <Controls />

                  <MiniMap
                    nodeStrokeWidth={3}
                    zoomable
                    pannable
                    nodeColor={(node) => {
                      switch (node.data?.type) {
                        case "api":
                          return "#93c5fd";
                        case "function":
                          return "#d8b4fe";
                        case "trigger":
                          return "#fcd34d";
                        case "data":
                          return "#86efac";
                        case "ai":
                          return "#a5b4fc";
                        case "chatTrigger":
                          return "#fdba74";
                        default:
                          return "#e2e8f0";
                      }
                    }}
                  />

                  <Panel position="top-left" className="m-4">
                    <WorkflowControls
                      isRunning={isRunning}
                      onRun={handleRunWorkflow}
                      onPause={handlePauseWorkflow}
                      onSave={() => alert("Workflow saved")}
                      onUndo={handleUndo}
                      onRedo={handleRedo}
                      canUndo={canUndo}
                      canRedo={canRedo}
                      onDuplicate={handleDuplicateSelectedNodes}
                      onExport={handleExportWorkflow}
                      onImport={handleImportWorkflow}
                    />
                  </Panel>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="application/json"
                    className="hidden"
                    onChange={handleWorkflowFileSelected}
                  />
                </ReactFlow>
              </div>
            </div>
          </TabsContent>

          <TabsContent
            value="execution"
            className="flex-1 m-0 p-0 overflow-hidden min-h-0"
          >
            <WorkflowExecutionHistory
              executions={mockExecutions.map((execution) => ({
                ...execution,
                nodes: execution.nodes.map((node) => ({
                  ...node,
                  status: node.status || ("idle" as NodeStatus),
                })),
              }))}
              onViewDetails={handleViewExecutionDetails}
              onRefresh={() =>
                toast({
                  title: "Execution history refresh",
                  description:
                    "Live execution syncing will be added once the backend is connected.",
                })
              }
              onCopyToEditor={(execution) =>
                toast({
                  title: "Copied execution context",
                  description: `Run ${execution.runId} will be available in the editor soon.`,
                })
              }
              onDelete={(execution) =>
                toast({
                  title: "Execution deletion coming soon",
                  description: `Run ${execution.runId} can be removed once persistence is implemented.`,
                })
              }
            />
          </TabsContent>

          <TabsContent value="settings" className="m-0 p-4 overflow-auto">
            <div className="max-w-3xl mx-auto space-y-8">
              <div>
                <h2 className="text-xl font-bold mb-4">Workflow Settings</h2>
                <div className="space-y-4">
                  <div className="grid gap-2">
                    <label className="text-sm font-medium">Workflow Name</label>
                    <input
                      type="text"
                      className="border border-border rounded-md px-3 py-2 bg-background"
                      value={workflowName}
                      onChange={(e) => setWorkflowName(e.target.value)}
                    />
                  </div>
                  <div className="grid gap-2">
                    <label className="text-sm font-medium">Description</label>
                    <textarea
                      className="border border-border rounded-md px-3 py-2 bg-background"
                      rows={3}
                      defaultValue="This is a marketing automation workflow."
                    />
                  </div>
                  <div className="grid gap-2">
                    <label className="text-sm font-medium">Tags</label>
                    <input
                      type="text"
                      className="border border-border rounded-md px-3 py-2 bg-background"
                      defaultValue="marketing, automation"
                    />

                    <p className="text-xs text-muted-foreground">
                      Separate tags with commas
                    </p>
                  </div>
                </div>
              </div>

              <Separator />

              <div>
                <h2 className="text-xl font-bold mb-4">Execution Settings</h2>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <label className="text-sm font-medium">
                        Timeout (seconds)
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Maximum execution time for the workflow
                      </p>
                    </div>
                    <input
                      type="number"
                      className="border border-border rounded-md px-3 py-2 bg-background w-24"
                      defaultValue="300"
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <label className="text-sm font-medium">
                        Retry on Failure
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Automatically retry the workflow if it fails
                      </p>
                    </div>
                    <div className="flex items-center h-6">
                      <input
                        type="checkbox"
                        className="h-4 w-4"
                        defaultChecked
                      />
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <label className="text-sm font-medium">
                        Maximum Retries
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Number of retry attempts before giving up
                      </p>
                    </div>
                    <input
                      type="number"
                      className="border border-border rounded-md px-3 py-2 bg-background w-24"
                      defaultValue="3"
                    />
                  </div>
                </div>
              </div>

              <Separator />

              <div>
                <h2 className="text-xl font-bold mb-4">Notifications</h2>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <label className="text-sm font-medium">
                        Email Notifications
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Send email when workflow fails
                      </p>
                    </div>
                    <div className="flex items-center h-6">
                      <input
                        type="checkbox"
                        className="h-4 w-4"
                        defaultChecked
                      />
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <label className="text-sm font-medium">
                        Slack Notifications
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Send Slack message when workflow completes
                      </p>
                    </div>
                    <div className="flex items-center h-6">
                      <input type="checkbox" className="h-4 w-4" />
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="outline">Cancel</Button>
                <Button>Save Settings</Button>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </div>

      {selectedNode && (
        <NodeInspector
          node={{
            id: selectedNode.id,
            type: selectedNode.type || "default",
            data: selectedNode.data,
          }}
          onClose={handleCloseNodeInspector}
          onSave={handleNodeUpdate}
          className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-50"
        />
      )}

      {/* Chat Interface */}
      {isChatOpen && (
        <ChatInterface
          title={chatTitle}
          user={user}
          ai={ai}
          isClosable={true}
          onSendMessage={handleSendChatMessage}
          position="bottom-right"
          initialMessages={[
            {
              id: "welcome-msg",
              content: `Welcome to the ${chatTitle} interface. How can I help you today?`,
              sender: {
                ...ai,
                isAI: true,
              },
              timestamp: new Date(),
            },
          ]}
        />
      )}
    </div>
  );
}
