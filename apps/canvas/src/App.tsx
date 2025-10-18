import { FormEvent, useEffect, useMemo, useReducer, useState } from "react";
import "./app.css";

type CanvasNode = {
  id: string;
  type: string;
  label: string;
  position: { x: number; y: number };
  data: Record<string, unknown>;
};

type Snapshot = {
  nodes: CanvasNode[];
  selectedId: string | null;
  scale: number;
  offset: { x: number; y: number };
  nextId: number;
};

type DesignerState = Snapshot & {
  history: {
    past: Snapshot[];
    future: Snapshot[];
  };
};

type DesignerAction =
  | { type: "ADD_NODE"; nodeType: string; label: string }
  | { type: "SELECT_NODE"; nodeId: string | null }
  | { type: "SET_LABEL"; nodeId: string; label: string }
  | { type: "NUDGE"; dx: number; dy: number }
  | { type: "DUPLICATE" }
  | { type: "DELETE" }
  | { type: "PAN"; dx: number; dy: number }
  | { type: "ZOOM_IN" }
  | { type: "ZOOM_OUT" }
  | { type: "UNDO" }
  | { type: "REDO" }
  | { type: "REPLACE_NODES"; nodes: CanvasNode[] };

const initialState: DesignerState = {
  nodes: [],
  selectedId: null,
  scale: 1,
  offset: { x: 0, y: 0 },
  nextId: 0,
  history: { past: [], future: [] },
};

function cloneNode(node: CanvasNode): CanvasNode {
  return {
    ...node,
    position: { ...node.position },
    data: { ...node.data },
  };
}

function cloneNodes(nodes: CanvasNode[]): CanvasNode[] {
  return nodes.map(cloneNode);
}

function snapshotFrom(state: DesignerState): Snapshot {
  return {
    nodes: cloneNodes(state.nodes),
    selectedId: state.selectedId,
    scale: state.scale,
    offset: { ...state.offset },
    nextId: state.nextId,
  };
}

function commit(previous: DesignerState, next: DesignerState): DesignerState {
  return {
    ...next,
    history: {
      past: [...previous.history.past, snapshotFrom(previous)],
      future: [],
    },
  };
}

function nextPosition(nodeCount: number): { x: number; y: number } {
  const spacing = 140;
  const row = Math.floor(nodeCount / 3);
  const column = nodeCount % 3;
  return { x: column * spacing, y: row * spacing };
}

function sanitizeNodes(nodes: CanvasNode[]): CanvasNode[] {
  return nodes.map((node, index) => {
    const position = node.position ?? nextPosition(index);
    return {
      ...node,
      position: { x: position.x ?? 0, y: position.y ?? 0 },
      data: node.data ?? {},
    };
  });
}

function reducer(state: DesignerState, action: DesignerAction): DesignerState {
  switch (action.type) {
    case "ADD_NODE": {
      const id = `node-${state.nextId + 1}`;
      const newNode: CanvasNode = {
        id,
        type: action.nodeType,
        label: action.label,
        position: nextPosition(state.nodes.length),
        data: {},
      };
      const next: DesignerState = {
        ...state,
        nodes: [...cloneNodes(state.nodes), newNode],
        selectedId: id,
        nextId: state.nextId + 1,
      };
      return commit(state, next);
    }
    case "SELECT_NODE": {
      if (state.selectedId === action.nodeId) {
        return state;
      }
      return { ...state, selectedId: action.nodeId };
    }
    case "SET_LABEL": {
      const nodes = state.nodes.map((node) =>
        node.id === action.nodeId ? { ...node, label: action.label } : node,
      );
      const next: DesignerState = { ...state, nodes: sanitizeNodes(nodes) };
      return commit(state, next);
    }
    case "NUDGE": {
      if (!state.selectedId) {
        return state;
      }
      const nodes = state.nodes.map((node) =>
        node.id === state.selectedId
          ? {
              ...node,
              position: {
                x: node.position.x + action.dx,
                y: node.position.y + action.dy,
              },
            }
          : node,
      );
      const next: DesignerState = { ...state, nodes: sanitizeNodes(nodes) };
      return commit(state, next);
    }
    case "DUPLICATE": {
      if (!state.selectedId) {
        return state;
      }
      const original = state.nodes.find((node) => node.id === state.selectedId);
      if (!original) {
        return state;
      }
      const id = `node-${state.nextId + 1}`;
      const copy: CanvasNode = {
        ...cloneNode(original),
        id,
        label: `${original.label} Copy`,
        position: {
          x: original.position.x + 32,
          y: original.position.y + 32,
        },
      };
      const next: DesignerState = {
        ...state,
        nodes: [...cloneNodes(state.nodes), copy],
        selectedId: id,
        nextId: state.nextId + 1,
      };
      return commit(state, next);
    }
    case "DELETE": {
      if (!state.selectedId) {
        return state;
      }
      const nodes = state.nodes.filter((node) => node.id !== state.selectedId);
      const next: DesignerState = {
        ...state,
        nodes,
        selectedId: nodes.at(-1)?.id ?? null,
      };
      return commit(state, next);
    }
    case "PAN": {
      return {
        ...state,
        offset: {
          x: state.offset.x + action.dx,
          y: state.offset.y + action.dy,
        },
      };
    }
    case "ZOOM_IN": {
      return { ...state, scale: Math.min(state.scale + 0.1, 2) };
    }
    case "ZOOM_OUT": {
      return { ...state, scale: Math.max(state.scale - 0.1, 0.5) };
    }
    case "UNDO": {
      if (state.history.past.length === 0) {
        return state;
      }
      const previous = state.history.past.at(-1);
      if (!previous) {
        return state;
      }
      const remainingPast = state.history.past.slice(0, -1);
      const future = [snapshotFrom(state), ...state.history.future];
      return {
        ...state,
        ...previous,
        nodes: cloneNodes(previous.nodes),
        offset: { ...previous.offset },
        history: { past: remainingPast, future },
      };
    }
    case "REDO": {
      if (state.history.future.length === 0) {
        return state;
      }
      const [nextSnapshot, ...remainingFuture] = state.history.future;
      return {
        ...state,
        ...nextSnapshot,
        nodes: cloneNodes(nextSnapshot.nodes),
        offset: { ...nextSnapshot.offset },
        history: {
          past: [...state.history.past, snapshotFrom(state)],
          future: remainingFuture,
        },
      };
    }
    case "REPLACE_NODES": {
      const sanitized = sanitizeNodes(action.nodes);
      const nextId = sanitized.reduce((max, node) => {
        const match = /node-(\d+)/u.exec(node.id);
        if (!match) {
          return max;
        }
        return Math.max(max, Number.parseInt(match[1], 10));
      }, 0);
      const next: DesignerState = {
        ...state,
        nodes: sanitized,
        selectedId: sanitized.at(-1)?.id ?? null,
        nextId,
      };
      return commit(state, next);
    }
    default:
      return state;
  }
}

function useDesignerState() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const selectedNode = useMemo(
    () => state.nodes.find((node) => node.id === state.selectedId),
    [state.nodes, state.selectedId],
  );

  return {
    state,
    selectedNode,
    canUndo: state.history.past.length > 0,
    canRedo: state.history.future.length > 0,
    addNode: (nodeType: string, label: string) =>
      dispatch({ type: "ADD_NODE", nodeType, label }),
    selectNode: (nodeId: string | null) =>
      dispatch({ type: "SELECT_NODE", nodeId }),
    setLabel: (nodeId: string, label: string) =>
      dispatch({ type: "SET_LABEL", nodeId, label }),
    nudgeSelected: (dx: number, dy: number) =>
      dispatch({ type: "NUDGE", dx, dy }),
    duplicateSelected: () => dispatch({ type: "DUPLICATE" }),
    deleteSelected: () => dispatch({ type: "DELETE" }),
    pan: (dx: number, dy: number) => dispatch({ type: "PAN", dx, dy }),
    zoomIn: () => dispatch({ type: "ZOOM_IN" }),
    zoomOut: () => dispatch({ type: "ZOOM_OUT" }),
    undo: () => dispatch({ type: "UNDO" }),
    redo: () => dispatch({ type: "REDO" }),
    replaceNodes: (nodes: CanvasNode[]) =>
      dispatch({ type: "REPLACE_NODES", nodes }),
  };
}

const palette = [
  { label: "Webhook Trigger", type: "trigger.webhook" },
  { label: "Cron Trigger", type: "trigger.cron" },
  { label: "OpenAI Completion", type: "ai.openai" },
  { label: "Anthropic Claude", type: "ai.anthropic" },
  { label: "HTTP Request", type: "data.http" },
  { label: "JSON Transform", type: "logic.json" },
  { label: "If/Else Branch", type: "logic.branch" },
  { label: "Slack Message", type: "comm.slack" },
];

type ChatMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};

function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "system",
      content: "Chat session initialised. Ask the agent to execute test runs.",
    },
  ]);
  const [input, setInput] = useState("");

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) {
      return;
    }
    setMessages((current) => [
      ...current,
      { role: "user", content: trimmed },
      {
        role: "assistant",
        content: `Simulated hand-off response for: ${trimmed}`,
      },
    ]);
    setInput("");
  };

  return (
    <section className="chat-panel">
      <h2>Workflow Chat Handoff</h2>
      <div className="chat-log" role="log">
        {messages.map((message, index) => (
          <div key={index} className={`chat-message ${message.role}`}>
            <strong>{message.role === "assistant" ? "Orcheo" : message.role}:</strong>
            <span>{message.content}</span>
          </div>
        ))}
      </div>
      <form className="chat-input" onSubmit={handleSubmit}>
        <label htmlFor="chat-entry">Ask the canvas copilot</label>
        <textarea
          id="chat-entry"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          rows={2}
          placeholder="Explain how to replay this workflow run..."
        />
        <button type="submit">Send</button>
      </form>
    </section>
  );
}

function useWorkflowMetrics(nodes: CanvasNode[]) {
  return useMemo(() => {
    const triggers = nodes.filter((node) => node.type.startsWith("trigger")).length;
    const aiNodes = nodes.filter((node) => node.type.startsWith("ai")).length;
    const estimatedTokens = aiNodes * 128;
    return {
      totalNodes: nodes.length,
      triggers,
      aiNodes,
      estimatedTokens,
    };
  }, [nodes]);
}

export function App() {
  const {
    state,
    selectedNode,
    canUndo,
    canRedo,
    addNode,
    selectNode,
    setLabel,
    nudgeSelected,
    duplicateSelected,
    deleteSelected,
    pan,
    zoomIn,
    zoomOut,
    undo,
    redo,
    replaceNodes,
  } = useDesignerState();
  const { nodes, scale, offset } = state;
  const metrics = useWorkflowMetrics(nodes);
  const [jsonDraft, setJsonDraft] = useState<string>(() =>
    JSON.stringify(nodes, null, 2),
  );
  const [lastExport, setLastExport] = useState<string>("");
  const [importError, setImportError] = useState<string | null>(null);

  useEffect(() => {
    setJsonDraft(JSON.stringify(nodes, null, 2));
  }, [nodes]);

  const diffLines = useMemo(() => {
    if (!lastExport) {
      return [];
    }
    const previous = lastExport.split("\n");
    const current = jsonDraft.split("\n");
    const longest = Math.max(previous.length, current.length);
    const result: string[] = [];
    for (let index = 0; index < longest; index += 1) {
      if (previous[index] === current[index]) {
        continue;
      }
      const before = previous[index] ?? "";
      const after = current[index] ?? "";
      result.push(`-${before}`);
      result.push(`+${after}`);
    }
    return result;
  }, [jsonDraft, lastExport]);

  const handleImport = () => {
    try {
      const parsed = JSON.parse(jsonDraft);
      if (!Array.isArray(parsed)) {
        throw new Error("Workflow JSON must be an array of nodes");
      }
      const normalised: CanvasNode[] = parsed.map((node, index) => ({
        id: typeof node.id === "string" ? node.id : `node-${index + 1}`,
        type: typeof node.type === "string" ? node.type : "custom",
        label: typeof node.label === "string" ? node.label : `Node ${index + 1}`,
        position: {
          x: Number(node.position?.x ?? index * 120),
          y: Number(node.position?.y ?? 0),
        },
        data: typeof node.data === "object" && node.data !== null ? node.data : {},
      }));
      replaceNodes(normalised);
      setImportError(null);
    } catch (error) {
      setImportError(error instanceof Error ? error.message : "Failed to import workflow");
    }
  };

  const handleExport = () => {
    const payload = JSON.stringify(nodes, null, 2);
    setJsonDraft(payload);
    setLastExport(payload);
    setImportError(null);
  };

  const handleClear = () => {
    setJsonDraft("[]");
  };

  return (
    <main className="app">
      <header className="toolbar">
        <div>
          <h1>Orcheo Canvas</h1>
          <p>
            Visual workflow designer with credential-aware validation, live execution
            telemetry, and guided chat handoff.
          </p>
        </div>
        <div className="toolbar-controls">
          <button onClick={undo} disabled={!canUndo} aria-label="Undo">
            Undo
          </button>
          <button onClick={redo} disabled={!canRedo} aria-label="Redo">
            Redo
          </button>
          <button onClick={() => pan(-40, 0)}>Pan Left</button>
          <button onClick={() => pan(40, 0)}>Pan Right</button>
          <button onClick={() => pan(0, -40)}>Pan Up</button>
          <button onClick={() => pan(0, 40)}>Pan Down</button>
          <button onClick={zoomIn}>Zoom In</button>
          <button onClick={zoomOut}>Zoom Out</button>
        </div>
      </header>

      <section className="designer">
        <aside className="palette" aria-label="node palette">
          <h2>Node Library</h2>
          <p>
            Drag-free controls let you assemble flows even on smaller screens. Click a
            template to drop it onto the canvas.
          </p>
          {palette.map((item) => (
            <button
              key={item.type}
              onClick={() => addNode(item.type, item.label)}
              className="palette-item"
            >
              Add {item.label}
            </button>
          ))}
          <section>
            <h3>Reusable Sub-workflows</h3>
            <p>
              Save frequently used branches and drop them into the canvas as reusable
              sub-flows to accelerate onboarding.
            </p>
          </section>
        </aside>

        <div className="canvas-wrapper">
          <div
            className="canvas-surface"
            data-testid="canvas-surface"
            style={{
              transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
            }}
          >
            {nodes.map((node) => (
              <button
                type="button"
                key={node.id}
                className={`canvas-node${state.selectedId === node.id ? " selected" : ""}`}
                style={{ left: `${node.position.x}px`, top: `${node.position.y}px` }}
                data-testid="canvas-node"
                onClick={() => selectNode(node.id)}
              >
                <span className="node-label">{node.label}</span>
                <span className="node-type">{node.type}</span>
              </button>
            ))}
          </div>
          <div className="minimap" aria-label="minimap">
            {nodes.map((node) => (
              <span
                key={node.id}
                className="minimap-node"
                style={{
                  left: `${node.position.x / 5 + 40}px`,
                  top: `${node.position.y / 5 + 40}px`,
                }}
              />
            ))}
          </div>
        </div>

        <aside className="inspector">
          <h2>Inspector</h2>
          {selectedNode ? (
            <div className="inspector-panel">
              <label>
                Label
                <input
                  value={selectedNode.label}
                  onChange={(event) => setLabel(selectedNode.id, event.target.value)}
                />
              </label>
              <p className="inspector-meta">Type: {selectedNode.type}</p>
              <div className="inspector-actions">
                <button onClick={() => nudgeSelected(0, -20)}>Nudge Up</button>
                <button onClick={() => nudgeSelected(0, 20)}>Nudge Down</button>
                <button onClick={() => nudgeSelected(-20, 0)}>Nudge Left</button>
                <button onClick={() => nudgeSelected(20, 0)}>Nudge Right</button>
                <button onClick={duplicateSelected}>Duplicate</button>
                <button onClick={deleteSelected}>Delete</button>
              </div>
            </div>
          ) : (
            <p>Select a node to edit its configuration, credentials, and testing hooks.</p>
          )}
          <section>
            <h3>Credential Management</h3>
            <p>
              Link nodes with vault-backed credential templates and publish-time
              validation ensures every automation passes secret governance checks.
            </p>
          </section>
          <section>
            <h3>Live Execution</h3>
            <ul>
              <li>Total nodes: {metrics.totalNodes}</li>
              <li>Trigger nodes: {metrics.triggers}</li>
              <li>AI nodes: {metrics.aiNodes}</li>
              <li>Estimated tokens/run: {metrics.estimatedTokens}</li>
            </ul>
          </section>
        </aside>
      </section>

      <section className="workflow-operations">
        <h2>Workflow Operations</h2>
        <p>
          Save and load workflow state, share JSON exports, and review diffs before
          publishing to production workspaces.
        </p>
        <textarea
          aria-label="Workflow JSON"
          value={jsonDraft}
          onChange={(event) => setJsonDraft(event.target.value)}
        />
        <div className="workflow-buttons">
          <button onClick={handleExport}>Export JSON</button>
          <button onClick={handleImport}>Import JSON</button>
          <button onClick={handleClear}>Clear Editor</button>
        </div>
        {importError ? <p role="alert">{importError}</p> : null}
        <details>
          <summary>Version Diff Viewer</summary>
          {diffLines.length === 0 ? (
            <p>No changes since last export.</p>
          ) : (
            <pre className="diff-viewer" aria-label="diff output">
              {diffLines.join("\n")}
            </pre>
          )}
        </details>
        <section className="shareable-links">
          <h3>Shareable Exports</h3>
          <p>
            Generate read-only previews and embed quickstart templates that match your
            team&apos;s governance policies.
          </p>
        </section>
      </section>

      <ChatPanel />
    </main>
  );
}
