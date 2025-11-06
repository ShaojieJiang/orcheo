import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import type { EdgeChange, NodeChange } from "@xyflow/react";
import { useEdgesState, useNodesState } from "@xyflow/react";

import {
  cloneEdge,
  cloneNode,
} from "@features/workflow/pages/workflow-canvas/helpers/clipboard";
import type {
  CanvasEdge,
  CanvasNode,
  WorkflowSnapshot,
} from "@features/workflow/pages/workflow-canvas/helpers/types";

const HISTORY_LIMIT = 50;

type UseWorkflowCanvasHistoryOptions = {
  initialNodes: CanvasNode[];
  initialEdges: CanvasEdge[];
};

type SetStateAction<T> = React.SetStateAction<T>;

export interface WorkflowCanvasHistory {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  nodesRef: React.MutableRefObject<CanvasNode[]>;
  edgesRef: React.MutableRefObject<CanvasEdge[]>;
  latestNodesRef: React.MutableRefObject<CanvasNode[]>;
  isRestoringRef: React.MutableRefObject<boolean>;
  onNodesChange: (changes: NodeChange<CanvasNode>[]) => void;
  onEdgesChange: (changes: EdgeChange<CanvasEdge>[]) => void;
  setNodes: (updater: SetStateAction<CanvasNode[]>) => void;
  setEdges: (updater: SetStateAction<CanvasEdge[]>) => void;
  setNodesState: React.Dispatch<SetStateAction<CanvasNode[]>>;
  setEdgesState: React.Dispatch<SetStateAction<CanvasEdge[]>>;
  createSnapshot: () => WorkflowSnapshot;
  recordSnapshot: (options?: { force?: boolean }) => void;
  applySnapshot: (
    snapshot: WorkflowSnapshot,
    options?: { resetHistory?: boolean },
  ) => void;
  handleUndo: () => void;
  handleRedo: () => void;
  canUndo: boolean;
  canRedo: boolean;
}

export function useWorkflowCanvasHistory({
  initialNodes,
  initialEdges,
}: UseWorkflowCanvasHistoryOptions): WorkflowCanvasHistory {
  const [nodes, setNodesState, onNodesChangeState] =
    useNodesState<CanvasNode>(initialNodes);
  const [edges, setEdgesState, onEdgesChangeState] =
    useEdgesState<CanvasEdge>(initialEdges);

  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  const nodesRef = useRef<CanvasNode[]>(nodes);
  const edgesRef = useRef<CanvasEdge[]>(edges);
  const latestNodesRef = useRef<CanvasNode[]>(nodes);
  const undoStackRef = useRef<WorkflowSnapshot[]>([]);
  const redoStackRef = useRef<WorkflowSnapshot[]>([]);
  const isRestoringRef = useRef(false);

  useEffect(() => {
    nodesRef.current = nodes;
    latestNodesRef.current = nodes;
  }, [nodes]);

  useEffect(() => {
    edgesRef.current = edges;
  }, [edges]);

  useLayoutEffect(() => {
    if (isRestoringRef.current) {
      isRestoringRef.current = false;
    }
  }, [nodes, edges]);

  const createSnapshot = useCallback((): WorkflowSnapshot => {
    return {
      nodes: nodesRef.current.map(cloneNode),
      edges: edgesRef.current.map(cloneEdge),
    };
  }, []);

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
    (snapshot: WorkflowSnapshot, options?: { resetHistory?: boolean }) => {
      isRestoringRef.current = true;
      setNodesState(snapshot.nodes);
      setEdgesState(snapshot.edges);
      if (options?.resetHistory) {
        undoStackRef.current = [];
        redoStackRef.current = [];
        setCanUndo(false);
        setCanRedo(false);
      }
    },
    [setNodesState, setEdgesState],
  );

  const setNodes = useCallback(
    (updater: SetStateAction<CanvasNode[]>) => {
      if (!isRestoringRef.current) {
        recordSnapshot();
      }
      setNodesState((current) =>
        typeof updater === "function"
          ? (updater as (value: CanvasNode[]) => CanvasNode[])(current)
          : updater,
      );
    },
    [recordSnapshot, setNodesState],
  );

  const setEdges = useCallback(
    (updater: SetStateAction<CanvasEdge[]>) => {
      if (!isRestoringRef.current) {
        recordSnapshot();
      }
      setEdgesState((current) =>
        typeof updater === "function"
          ? (updater as (value: CanvasEdge[]) => CanvasEdge[])(current)
          : updater,
      );
    },
    [recordSnapshot, setEdgesState],
  );

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

  const onNodesChange = useCallback(
    (changes: NodeChange<CanvasNode>[]) => {
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

  const onEdgesChange = useCallback(
    (changes: EdgeChange<CanvasEdge>[]) => {
      if (changes.some((change) => change.type !== "select")) {
        recordSnapshot();
      }
      onEdgesChangeState(changes);
    },
    [onEdgesChangeState, recordSnapshot],
  );

  return {
    nodes,
    edges,
    nodesRef,
    edgesRef,
    latestNodesRef,
    isRestoringRef,
    onNodesChange,
    onEdgesChange,
    setNodes,
    setEdges,
    setNodesState,
    setEdgesState,
    createSnapshot,
    recordSnapshot,
    applySnapshot,
    handleUndo,
    handleRedo,
    canUndo,
    canRedo,
  };
}
