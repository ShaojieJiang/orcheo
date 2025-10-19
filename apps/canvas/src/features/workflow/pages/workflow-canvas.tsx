import React, { useState, useCallback, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  ReactFlow,
  Background,
  Controls,
  Edge,
  Node,
  NodeChange,
  Connection,
  OnConnect,
  OnEdgesChange,
  OnNodesChange,
  Panel,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  getIncomers,
  getOutgoers,
  getConnectedEdges,
  useReactFlow,
  useNodesState,
  useEdgesState,
  MarkerType,
  ConnectionLineType,
  MiniMap,
  NodeProps,
  NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { Button } from "@/design-system/ui/button";
import { Tabs, TabsContent } from "@/design-system/ui/tabs";
import { Badge } from "@/design-system/ui/badge";
import { Separator } from "@/design-system/ui/separator";
import { Search, Plus, MessageSquare, Clock, AlertCircle } from "lucide-react";

import TopNavigation from "@features/shared/components/top-navigation";
import SidebarPanel from "@features/workflow/components/panels/sidebar-panel";
import WorkflowNode from "@features/workflow/components/nodes/workflow-node";
import WorkflowControls from "@features/workflow/components/canvas/workflow-controls";
import NodeInspector from "@features/workflow/components/panels/node-inspector";
import ChatTriggerNode from "@features/workflow/components/nodes/chat-trigger-node";
import ChatInterface from "@features/shared/components/chat-interface";
import WorkflowExecutionHistory from "@features/workflow/components/panels/workflow-execution-history";
import WorkflowTabs from "@features/workflow/components/panels/workflow-tabs";
import { SAMPLE_WORKFLOWS } from "@features/workflow/data/workflow-data";
import StartEndNode from "@features/workflow/components/nodes/start-end-node";

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
type WorkflowEdge = Edge<any>;

// Update the WorkflowExecution interface to match the component's expectations
type WorkflowExecutionStatus = "running" | "success" | "failed" | "partial";
type NodeStatus = "idle" | "running" | "success" | "error" | "warning";

interface WorkflowExecutionNode {
  id: string;
  type: string;
  name: string;
  position: { x: number; y: number };
  status: NodeStatus;
  details?: any;
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

interface NodeInspectorProps {
  node: Node<NodeData>;
  onClose: () => void;
  onSave: (nodeId: string, data: Partial<NodeData>) => void;
  className?: string;
}

interface ChatMessageProps {
  id: string;
  content: string;
  sender: {
    id: string;
    name: string;
    avatar: string;
    isAI?: boolean;
  };
  timestamp: Date;
}

interface WorkflowControlsProps {
  isRunning: boolean;
  onRun: () => void;
  onPause: () => void;
  onSave: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onZoomToFit: () => void;
  canUndo: boolean;
  canRedo: boolean;
}

interface ChatInterfaceProps {
  title: string;
  user: {
    id: string;
    name: string;
    avatar: string;
  };
  ai: {
    id: string;
    name: string;
    avatar: string;
  };
  isClosable: boolean;
  onSendMessage: (message: string, attachments: any[]) => void;
  position: "bottom-right";
  initialMessages: Array<{
    id: string;
    content: string;
    role: "user" | "assistant";
    timestamp: string;
  }>;
}

// Import WorkflowExecution type from the history component
import type { WorkflowExecution as HistoryWorkflowExecution } from "@features/workflow/components/panels/workflow-execution-history";

export default function WorkflowCanvas() {
  const navigate = useNavigate();

  // Initialize with empty arrays instead of sample workflow
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<NodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  // State for UI controls
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [selectedExecution, setSelectedExecution] =
    useState<WorkflowExecution | null>(null);
  const [executions, setExecutions] = useState<WorkflowExecution[]>([]);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);
  const [selectedNode, setSelectedNode] = useState<WorkflowNode | null>(null);
  const [activeTab, setActiveTab] = useState("canvas");

  // Chat interface state
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [activeChatNodeId, setActiveChatNodeId] = useState<string | null>(null);
  const [chatTitle, setChatTitle] = useState("Chat");

  // Refs
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const reactFlowInstance = useRef<any>(null);

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
        setCanUndo(true);
      }
    },
    [edges, setEdges],
  );

  // Handle node selection
  const onNodeClick = useCallback((_: React.MouseEvent, node: WorkflowNode) => {
    // Only handle single clicks here, but don't set selected node
    if (_.detail === 1) {
      // Do nothing for single clicks
    }
  }, []);

  // Handle node double click for inspection
  const onNodeDoubleClick = useCallback(
    (_: React.MouseEvent, node: WorkflowNode) => {
      setSelectedNode(node);
    },
    [],
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
        const node = JSON.parse(nodeData);

        // Get the position where the node was dropped
        const position = reactFlowInstance.current.project({
          x: event.clientX - reactFlowBounds.left,
          y: event.clientY - reactFlowBounds.top,
        });

        // Determine node type
        let nodeType = "default";
        if (node.id?.includes("chat-trigger")) {
          nodeType = "chatTrigger";
        } else if (node.id === "start-node" || node.id === "end-node") {
          nodeType = "startEnd";
        }

        // Create a new node
        const newNode: WorkflowNode = {
          id: `node-${Date.now()}`,
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
                ? () => handleOpenChat(`node-${Date.now()}`)
                : undefined,
          },
          draggable: true,
        };

        // Add the new node to the canvas
        setNodes((nds) => nds.concat(newNode));

        // Enable undo after adding a node
        setCanUndo(true);
      } catch (error) {
        console.error("Error adding new node:", error);
      }
    },
    [setNodes],
  );

  // Handle adding a node by clicking
  const handleAddNode = useCallback(
    (node: any) => {
      if (!reactFlowInstance.current) return;

      // Determine node type
      let nodeType = "default";
      if (node.id?.includes("chat-trigger")) {
        nodeType = "chatTrigger";
      } else if (node.id === "start-node" || node.id === "end-node") {
        nodeType = "startEnd";
      }

      // Calculate a position for the new node
      const position = {
        x: Math.random() * 300 + 100,
        y: Math.random() * 300 + 100,
      };

      // Create a new node with explicit NodeData type
      const newNode: Node<NodeData> = {
        id: `node-${Date.now()}`,
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
              ? () => handleOpenChat(`node-${Date.now()}`)
              : undefined,
        },
        draggable: true,
      };

      // Add the new node to the canvas with type assertion
      setNodes((nds) => [...nds, newNode] as Node<NodeData>[]);
      setCanUndo(true);
    },
    [setNodes],
  );

  // Handle opening chat for a specific node
  const handleOpenChat = (nodeId: string) => {
    const chatNode = nodes.find((node) => node.id === nodeId) as Node<NodeData>;
    if (chatNode) {
      setChatTitle(chatNode.data.label || "Chat");
      setActiveChatNodeId(nodeId);
      setIsChatOpen(true);
    }
  };

  // Handle chat message sending
  const handleSendChatMessage = (message: string, attachments: any[]) => {
    console.log(`Message sent from node ${activeChatNodeId}:`, message);
    console.log("Attachments:", attachments);

    // Here you would typically process the message and trigger the workflow
    // For now, we'll just update the node status to simulate activity
    if (activeChatNodeId) {
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
    }
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

  // Handle zoom controls
  const handleZoomIn = useCallback(() => {
    if (reactFlowInstance.current) {
      reactFlowInstance.current.zoomIn();
    }
  }, []);

  const handleZoomOut = useCallback(() => {
    if (reactFlowInstance.current) {
      reactFlowInstance.current.zoomOut();
    }
  }, []);

  const handleZoomToFit = useCallback(() => {
    if (reactFlowInstance.current) {
      reactFlowInstance.current.fitView({ padding: 0.2 });
    }
  }, []);

  // Handle undo/redo (simplified implementation)
  const handleUndo = useCallback(() => {
    // In a real implementation, you would use a history stack
    setCanUndo(false);
    setCanRedo(true);
  }, []);

  const handleRedo = useCallback(() => {
    // In a real implementation, you would use a history stack
    setCanRedo(false);
    setCanUndo(true);
  }, []);

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
      setSelectedExecution(execution as unknown as WorkflowExecution);
    },
    [setNodes],
  );

  // Fit view on initial render
  useEffect(() => {
    setTimeout(() => {
      if (reactFlowInstance.current) {
        reactFlowInstance.current.fitView({ padding: 0.2 });
      }
    }, 100);
  }, []);

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
          name: "Marketing Automation",
          path: ["Projects", "Marketing Automations", "Marketing Automation"],
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
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
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
                    />
                  </Panel>
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
              onRefresh={() => console.log("Refreshing executions")}
              onCopyToEditor={(execution) =>
                console.log("Copying to editor:", execution.runId)
              }
              onDelete={(execution) =>
                console.log("Deleting execution:", execution.runId)
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
                      defaultValue="Marketing Automation"
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
