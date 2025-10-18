import { useCallback, useMemo, useRef, useState } from "react";
import {
  addEdge,
  Connection,
  Edge,
  Node,
  OnEdgesChange,
  OnNodesChange,
  applyEdgeChanges,
  applyNodeChanges,
} from "reactflow";
import { nanoid } from "nanoid";

type WorkflowSnapshot = {
  nodes: Node[];
  edges: Edge[];
};

type WorkflowTemplate = {
  id: string;
  name: string;
  description: string;
  snapshot: WorkflowSnapshot;
};

type SubWorkflow = {
  id: string;
  name: string;
  nodeIds: string[];
};

export type CredentialAssignments = Record<string, string>;

export type VersionDiff = {
  versionA: string;
  versionB: string;
  addedNodes: string[];
  removedNodes: string[];
};

type UseWorkflowStateResult = {
  nodes: Node[];
  edges: Edge[];
  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
  onConnect: (connection: Connection) => void;
  selectedNodeId: string | null;
  selectNode: (nodeId: string | null) => void;
  addNode: (type: string) => void;
  duplicateSelected: () => void;
  deleteSelected: () => void;
  searchTerm: string;
  setSearchTerm: (value: string) => void;
  filteredNodes: Node[];
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  saveWorkflow: (label?: string) => void;
  loadWorkflow: (label?: string) => void;
  exportWorkflow: () => string;
  importWorkflow: (payload: string) => void;
  versions: string[];
  computeDiff: (versionA: string, versionB: string) => VersionDiff | null;
  shareWorkflow: () => string;
  templates: WorkflowTemplate[];
  applyTemplate: (templateId: string) => void;
  subWorkflows: SubWorkflow[];
  createSubWorkflow: (name: string) => void;
  applySubWorkflow: (subWorkflowId: string) => void;
  credentialAssignments: CredentialAssignments;
  assignCredential: (nodeId: string, credential: string) => void;
  validateForPublish: () => string[];
};

const STORAGE_KEY = "orcheo.workflow.snapshot";
const VERSIONS_KEY = "orcheo.workflow.versions";

const DEFAULT_NODES: Node[] = [
  {
    id: nanoid(),
    position: { x: 50, y: 80 },
    data: {
      label: "Webhook Trigger",
      type: "trigger",
      description: "Receives external events",
      requiresCredential: true,
    },
    type: "default",
  },
];

const DEFAULT_TEMPLATES: WorkflowTemplate[] = [
  {
    id: "welcome-playbook",
    name: "Welcome New Lead",
    description: "Webhook trigger, AI summarizer, and Slack notification.",
    snapshot: {
      nodes: [
        {
          id: "trigger",
          position: { x: 20, y: 80 },
          data: {
            label: "HTTP Trigger",
            type: "trigger",
            description: "Capture inbound webhook payload",
            requiresCredential: true,
          },
          type: "default",
        },
        {
          id: "ai",
          position: { x: 220, y: 60 },
          data: {
            label: "Summarize Lead",
            type: "ai",
            description: "Summarize conversation using OpenAI",
            requiresCredential: true,
          },
          type: "default",
        },
        {
          id: "slack",
          position: { x: 420, y: 120 },
          data: {
            label: "Notify Slack",
            type: "action",
            description: "Post update to the sales channel",
            requiresCredential: true,
          },
          type: "default",
        },
      ],
      edges: [
        { id: "t-ai", source: "trigger", target: "ai" },
        { id: "ai-slack", source: "ai", target: "slack" },
      ],
    },
  },
  {
    id: "nightly-sync",
    name: "Nightly Database Sync",
    description: "Cron trigger, PostgreSQL fetch, and S3 archival.",
    snapshot: {
      nodes: [
        {
          id: "cron",
          position: { x: 30, y: 60 },
          data: {
            label: "Cron Trigger",
            type: "trigger",
            description: "Runs nightly",
            requiresCredential: false,
          },
          type: "default",
        },
        {
          id: "postgres",
          position: { x: 220, y: 20 },
          data: {
            label: "Fetch Data",
            type: "data",
            description: "Query PostgreSQL",
            requiresCredential: true,
          },
          type: "default",
        },
        {
          id: "s3",
          position: { x: 420, y: 120 },
          data: {
            label: "Archive to Storage",
            type: "storage",
            description: "Persist dataset to S3",
            requiresCredential: true,
          },
          type: "default",
        },
      ],
      edges: [
        { id: "cron-pg", source: "cron", target: "postgres" },
        { id: "pg-s3", source: "postgres", target: "s3" },
      ],
    },
  },
];

function buildNode(type: string): Node {
  const id = nanoid();
  const baseData = {
    label: `${type} Node`,
    type,
    description: "Custom workflow node",
    requiresCredential: ["ai", "action", "trigger", "data", "storage"].includes(type),
  };
  return {
    id,
    position: { x: 120, y: 120 },
    data: baseData,
    type: "default",
  };
}

export function useWorkflowState(): UseWorkflowStateResult {
  const [nodes, setNodes] = useState<Node[]>(DEFAULT_NODES);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [versions, setVersions] = useState<string[]>(() => {
    if (typeof window === "undefined") return [];
    const stored = window.localStorage.getItem(VERSIONS_KEY);
    return stored ? (JSON.parse(stored) as string[]) : [];
  });
  const [credentialAssignments, setCredentialAssignments] = useState<
    CredentialAssignments
  >({});
  const [subWorkflows, setSubWorkflows] = useState<SubWorkflow[]>([]);
  const historyRef = useRef<WorkflowSnapshot[]>([{ nodes: DEFAULT_NODES, edges: [] }]);
  const historyIndexRef = useRef(0);

  const pushHistory = useCallback(
    (snapshot: WorkflowSnapshot) => {
      historyRef.current = historyRef.current
        .slice(0, historyIndexRef.current + 1)
        .concat(snapshot);
      historyIndexRef.current = historyRef.current.length - 1;
    },
    []
  );

  const applySnapshot = useCallback((snapshot: WorkflowSnapshot) => {
    setNodes(snapshot.nodes);
    setEdges(snapshot.edges);
  }, []);

  const recordState = useCallback(
    (nextNodes: Node[], nextEdges: Edge[]) => {
      pushHistory({ nodes: nextNodes, edges: nextEdges });
    },
    [pushHistory]
  );

  const onNodesChange: OnNodesChange = useCallback(
    (changes) => {
      setNodes((nds) => {
        const next = applyNodeChanges(changes, nds);
        recordState(next, edges);
        return next;
      });
    },
    [edges, recordState]
  );

  const onEdgesChange: OnEdgesChange = useCallback(
    (changes) => {
      setEdges((eds) => {
        const next = applyEdgeChanges(changes, eds);
        recordState(nodes, next);
        return next;
      });
    },
    [nodes, recordState]
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => {
        const next = addEdge(connection, eds);
        recordState(nodes, next);
        return next;
      });
    },
    [nodes, recordState]
  );

  const addNode = useCallback(
    (type: string) => {
      setNodes((current) => {
        const next = current.concat(buildNode(type));
        recordState(next, edges);
        return next;
      });
    },
    [edges, recordState]
  );

  const duplicateSelected = useCallback(() => {
    if (!selectedNodeId) return;
    setNodes((current) => {
      const node = current.find((item) => item.id === selectedNodeId);
      if (!node) return current;
      const clone: Node = {
        ...node,
        id: nanoid(),
        position: { x: node.position.x + 60, y: node.position.y + 40 },
      };
      const next = current.concat(clone);
      recordState(next, edges);
      return next;
    });
  }, [edges, recordState, selectedNodeId]);

  const deleteSelected = useCallback(() => {
    if (!selectedNodeId) return;
    setNodes((current) => {
      const next = current.filter((node) => node.id !== selectedNodeId);
      if (next.length === current.length) return current;
      const nextEdges = edges.filter(
        (edge) => edge.source !== selectedNodeId && edge.target !== selectedNodeId,
      );
      setEdges(nextEdges);
      recordState(next, nextEdges);
      return next;
    });
  }, [edges, recordState, selectedNodeId]);

  const undo = useCallback(() => {
    if (historyIndexRef.current === 0) return;
    historyIndexRef.current -= 1;
    const snapshot = historyRef.current[historyIndexRef.current];
    applySnapshot(snapshot);
  }, [applySnapshot]);

  const redo = useCallback(() => {
    if (historyIndexRef.current >= historyRef.current.length - 1) return;
    historyIndexRef.current += 1;
    const snapshot = historyRef.current[historyIndexRef.current];
    applySnapshot(snapshot);
  }, [applySnapshot]);

  const filteredNodes = useMemo(() => {
    if (!searchTerm) return nodes;
    const normalized = searchTerm.toLowerCase();
    return nodes.map((node) => ({
      ...node,
      data: {
        ...node.data,
      },
      style: {
        ...(node.style ?? {}),
        opacity:
          String(node.data.label).toLowerCase().includes(normalized) ||
          String(node.data.type).toLowerCase().includes(normalized)
            ? 1
            : 0.35,
      },
    }));
  }, [nodes, searchTerm]);

  const persistVersions = useCallback(
    (next: string[]) => {
      setVersions(next);
      if (typeof window !== "undefined") {
        window.localStorage.setItem(VERSIONS_KEY, JSON.stringify(next));
      }
    },
    []
  );

  const saveWorkflow = useCallback(
    (label = "latest") => {
      const snapshot: WorkflowSnapshot = { nodes, edges };
      if (typeof window !== "undefined") {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
      }
      const versionId = `${label}-${new Date().toISOString()}`;
      persistVersions(versions.concat(versionId));
      pushHistory(snapshot);
    },
    [edges, nodes, persistVersions, pushHistory, versions]
  );

  const loadWorkflow = useCallback(
    (label = "latest") => {
      if (typeof window === "undefined") return;
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const snapshot = JSON.parse(raw) as WorkflowSnapshot;
      applySnapshot(snapshot);
      pushHistory(snapshot);
    },
    [applySnapshot, pushHistory]
  );

  const exportWorkflow = useCallback(() => {
    const snapshot = { nodes, edges, credentials: credentialAssignments };
    return JSON.stringify(snapshot, null, 2);
  }, [credentialAssignments, edges, nodes]);

  const importWorkflow = useCallback(
    (payload: string) => {
      const parsed = JSON.parse(payload) as {
        nodes: Node[];
        edges: Edge[];
        credentials?: CredentialAssignments;
      };
      setNodes(parsed.nodes);
      setEdges(parsed.edges);
      setCredentialAssignments(parsed.credentials ?? {});
      recordState(parsed.nodes, parsed.edges);
    },
    [recordState]
  );

  const computeDiff = useCallback(
    (versionA: string, versionB: string) => {
      if (typeof window === "undefined") return null;
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (!stored) return null;
      const current = JSON.parse(stored) as WorkflowSnapshot;
      const nodesA = new Set(current.nodes.map((node) => node.data.label as string));
      const nodesB = new Set(nodes.map((node) => node.data.label as string));
      const added = [...nodesB].filter((item) => !nodesA.has(item));
      const removed = [...nodesA].filter((item) => !nodesB.has(item));
      return {
        versionA,
        versionB,
        addedNodes: added,
        removedNodes: removed,
      } satisfies VersionDiff;
    },
    [nodes]
  );

  const shareWorkflow = useCallback(() => {
    const snapshot = exportWorkflow();
    return typeof window === "undefined" ? snapshot : window.btoa(snapshot);
  }, [exportWorkflow]);

  const applyTemplate = useCallback((templateId: string) => {
    const template = DEFAULT_TEMPLATES.find((item) => item.id === templateId);
    if (!template) return;
    const normalizedNodes = template.snapshot.nodes.map((node) => ({
      ...node,
      id: nanoid(),
      position: { ...node.position },
    }));
    const idMap = new Map<string, string>();
    template.snapshot.nodes.forEach((node, index) => {
      idMap.set(node.id, normalizedNodes[index].id);
    });
    const normalizedEdges = template.snapshot.edges.map((edge) => ({
      ...edge,
      id: nanoid(),
      source: idMap.get(edge.source) ?? edge.source,
      target: idMap.get(edge.target) ?? edge.target,
    }));
    setNodes(normalizedNodes);
    setEdges(normalizedEdges);
    recordState(normalizedNodes, normalizedEdges);
  }, [recordState]);

  const createSubWorkflow = useCallback(
    (name: string) => {
      if (!selectedNodeId) return;
      const target = nodes.find((node) => node.id === selectedNodeId);
      if (!target) return;
      const newGroup: SubWorkflow = {
        id: nanoid(),
        name,
        nodeIds: nodes.map((node) => node.id),
      };
      setSubWorkflows((current) => current.concat(newGroup));
    },
    [nodes, selectedNodeId]
  );

  const applySubWorkflow = useCallback(
    (subWorkflowId: string) => {
      const subWorkflow = subWorkflows.find((item) => item.id === subWorkflowId);
      if (!subWorkflow) return;
      const existingNodes = nodes.filter((node) => subWorkflow.nodeIds.includes(node.id));
      const clones = existingNodes.map((node) => ({
        ...node,
        id: nanoid(),
        position: { x: node.position.x + 80, y: node.position.y + 80 },
      }));
      const nextNodes = nodes.concat(clones);
      setNodes(nextNodes);
      recordState(nextNodes, edges);
    },
    [edges, nodes, recordState, subWorkflows]
  );

  const assignCredential = useCallback((nodeId: string, credential: string) => {
    setCredentialAssignments((current) => ({ ...current, [nodeId]: credential }));
  }, []);

  const validateForPublish = useCallback(() => {
    const issues: string[] = [];
    if (nodes.length === 0) {
      issues.push("Workflow requires at least one node.");
    }
    nodes.forEach((node) => {
      if (!node.data.label) {
        issues.push(`Node ${node.id} is missing a label.`);
      }
      if (node.data.requiresCredential && !credentialAssignments[node.id]) {
        issues.push(`Node ${node.data.label} requires a credential assignment.`);
      }
    });
    return issues;
  }, [credentialAssignments, nodes]);

  return {
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    onConnect,
    selectedNodeId,
    selectNode: setSelectedNodeId,
    addNode,
    duplicateSelected,
    deleteSelected,
    searchTerm,
    setSearchTerm,
    filteredNodes,
    undo,
    redo,
    canUndo: historyIndexRef.current > 0,
    canRedo: historyIndexRef.current < historyRef.current.length - 1,
    saveWorkflow,
    loadWorkflow,
    exportWorkflow,
    importWorkflow,
    versions,
    computeDiff,
    shareWorkflow,
    templates: DEFAULT_TEMPLATES,
    applyTemplate,
    subWorkflows,
    createSubWorkflow,
    applySubWorkflow,
    credentialAssignments,
    assignCredential,
    validateForPublish,
  };
}
