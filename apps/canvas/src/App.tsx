import type { ChangeEvent, FormEvent } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactFlow, {
  Background,
  Connection,
  Controls,
  Edge,
  MiniMap,
  Node,
  addEdge,
  useEdgesState,
  useNodesState,
} from "reactflow";
import "reactflow/dist/style.css";

import "./app.css";

type FlowState = {
  nodes: Node[];
  edges: Edge[];
};

type TemplateSummary = {
  slug: string;
  name: string;
  description: string;
  scopes: string[];
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

const LOCAL_STORAGE_KEY = "orcheo-canvas-state";

const initialNodes: Node[] = [
  {
    id: "trigger",
    position: { x: 0, y: 80 },
    data: { label: "Webhook Trigger" },
    type: "input",
  },
  {
    id: "ai",
    position: { x: 280, y: 80 },
    data: { label: "AI Agent" },
  },
  {
    id: "output",
    position: { x: 560, y: 80 },
    data: { label: "Slack Notification" },
    type: "output",
  },
];

const initialEdges: Edge[] = [
  { id: "trigger-ai", source: "trigger", target: "ai" },
  { id: "ai-output", source: "ai", target: "output" },
];

export function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [executionLog, setExecutionLog] = useState<string[]>([]);
  const [chatLog, setChatLog] = useState<ChatMessage[]>([]);
  const [isConfigOpen, setConfigOpen] = useState(true);
  const [historyRevision, setHistoryRevision] = useState(0);
  const historyRef = useRef<FlowState[]>([{ nodes: initialNodes, edges: initialEdges }]);
  const redoRef = useRef<FlowState[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  const pushHistory = useCallback(
    (state: FlowState) => {
      historyRef.current.push(state);
      if (historyRef.current.length > 50) {
        historyRef.current.shift();
      }
      redoRef.current = [];
      setHistoryRevision((revision) => revision + 1);
    },
    []
  );

  const handleConnect = useCallback(
    (connection: Connection) =>
      setEdges((eds) => addEdge({ ...connection, type: "smoothstep" }, eds)),
    [setEdges]
  );

  const handleNodeClick = useCallback((_, node: Node) => {
    setSelectedNodeId(node.id);
  }, []);

  const applySearchHighlight = useCallback(
    (term: string) => {
      setNodes((current) =>
        current.map((node) => ({
          ...node,
          style:
            term.length > 0 &&
            String(node.data?.label ?? "")
              .toLowerCase()
              .includes(term.toLowerCase())
              ? { border: "2px solid #f59e0b" }
              : undefined,
        }))
      );
    },
    [setNodes]
  );

  const duplicateSelectedNode = useCallback(() => {
    if (!selectedNodeId) return;
    setNodes((current) => {
      const node = current.find((item) => item.id === selectedNodeId);
      if (!node) return current;
      const duplicate: Node = {
        ...node,
        id: `${node.id}-copy-${Date.now()}`,
        position: {
          x: node.position.x + 40,
          y: node.position.y + 40,
        },
        data: {
          ...node.data,
          label: `${node.data?.label ?? node.id} Copy`,
        },
      };
      const next = [...current, duplicate];
      pushHistory({ nodes: next, edges });
      return next;
    });
  }, [edges, pushHistory, selectedNodeId, setNodes]);

  const saveToLocalStorage = useCallback(() => {
    const payload = JSON.stringify({ nodes, edges });
    localStorage.setItem(LOCAL_STORAGE_KEY, payload);
  }, [edges, nodes]);

  const loadFromLocalStorage = useCallback(() => {
    const raw = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (!raw) return;
    try {
      const parsed: FlowState = JSON.parse(raw);
      setNodes(parsed.nodes);
      setEdges(parsed.edges);
      pushHistory(parsed);
    } catch (error) {
      console.error("Failed to load workflow", error);
    }
  }, [pushHistory, setEdges, setNodes]);

  const exportJson = useCallback(() => {
    const blob = new Blob([JSON.stringify({ nodes, edges }, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "workflow.json";
    anchor.click();
    URL.revokeObjectURL(url);
  }, [edges, nodes]);

  const importJson = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;
      file.text().then((content) => {
        try {
          const parsed: FlowState = JSON.parse(content);
          setNodes(parsed.nodes);
          setEdges(parsed.edges);
          pushHistory(parsed);
        } catch (error) {
          console.error("Failed to import workflow", error);
        }
      });
    },
    [pushHistory, setEdges, setNodes]
  );

  const undo = useCallback(() => {
    if (historyRef.current.length <= 1) return;
    const current = historyRef.current.pop();
    if (!current) return;
    redoRef.current.push(current);
    const previous = historyRef.current[historyRef.current.length - 1];
    setNodes(previous.nodes);
    setEdges(previous.edges);
  }, [setEdges, setNodes]);

  const redo = useCallback(() => {
    const next = redoRef.current.pop();
    if (!next) return;
    historyRef.current.push(next);
    setNodes(next.nodes);
    setEdges(next.edges);
  }, [setEdges, setNodes]);

  const applyTemplate = useCallback(
    (template: TemplateSummary) => {
      const templatedNodes: Node[] = [
        {
          id: `trigger-${template.slug}`,
          position: { x: 0, y: 0 },
          data: { label: `${template.name} Trigger` },
          type: "input",
        },
        {
          id: `action-${template.slug}`,
          position: { x: 250, y: 0 },
          data: { label: `${template.name} Action` },
        },
      ];
      const templatedEdges: Edge[] = [
        {
          id: `template-${template.slug}`,
          source: templatedNodes[0].id,
          target: templatedNodes[1].id,
        },
      ];
      setNodes(templatedNodes);
      setEdges(templatedEdges);
      pushHistory({ nodes: templatedNodes, edges: templatedEdges });
    },
    [pushHistory, setEdges, setNodes]
  );

  const connectWebSocket = useCallback(() => {
    if (typeof window === "undefined" || window.WebSocket === undefined) return;
    if (wsRef.current) {
      wsRef.current.close();
    }
    try {
      const socket = new WebSocket("ws://localhost:8000/ws/workflow/demo");
      socket.onmessage = (event) => {
        setExecutionLog((log) => [...log, event.data]);
      };
      socket.onopen = () => {
        socket.send(
          JSON.stringify({
            type: "run_workflow",
            execution_id: `exec-${Date.now()}`,
            graph_config: { nodes, edges },
            inputs: {},
          })
        );
      };
      wsRef.current = socket;
    } catch (error) {
      console.warn("Unable to connect to execution websocket", error);
    }
  }, [edges, nodes]);

  const sendChatMessage = useCallback((message: string) => {
    if (!message) return;
    setChatLog((log) => [
      ...log,
      { role: "user", content: message },
      { role: "assistant", content: "Workflow simulated successfully." },
    ]);
  }, []);

  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedNodeId) ?? null,
    [nodes, selectedNodeId]
  );

  const versionDiff = useMemo(() => {
    if (historyRef.current.length < 2) {
      return null;
    }
    const previous = historyRef.current[historyRef.current.length - 2];
    const current = historyRef.current[historyRef.current.length - 1];
    return {
      nodeDelta: current.nodes.length - previous.nodes.length,
      edgeDelta: current.edges.length - previous.edges.length,
    };
  }, [historyRevision]);

  useEffect(() => {
    applySearchHighlight(searchTerm);
  }, [applySearchHighlight, searchTerm]);

  useEffect(() => {
    if (typeof fetch === "undefined") return;
    fetch("/api/credential-templates")
      .then((response) => response.json())
      .then((data: TemplateSummary[]) => setTemplates(data))
      .catch(() => setTemplates([]));
  }, []);

  useEffect(() => () => wsRef.current?.close(), []);

  return (
    <main className="app">
      <header className="toolbar">
        <div className="toolbar-group">
          <button type="button" onClick={saveToLocalStorage} aria-label="Save workflow">
            Save
          </button>
          <button type="button" onClick={loadFromLocalStorage} aria-label="Load workflow">
            Load
          </button>
          <button type="button" onClick={exportJson} aria-label="Export workflow">
            Export
          </button>
          <label className="import-label" htmlFor="import-json">
            Import
            <input
              id="import-json"
              type="file"
              accept="application/json"
              onChange={importJson}
            />
          </label>
        </div>
        <div className="toolbar-group">
          <button type="button" onClick={undo} aria-label="Undo">
            Undo
          </button>
          <button type="button" onClick={redo} aria-label="Redo">
            Redo
          </button>
          <button type="button" onClick={duplicateSelectedNode} aria-label="Duplicate selected node">
            Duplicate
          </button>
        </div>
        <div className="toolbar-group">
          <input
            type="search"
            placeholder="Search nodes"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
          />
          <button type="button" onClick={connectWebSocket} aria-label="Run workflow">
            Run
          </button>
        </div>
      </header>

      <section className="canvas-layout">
        <div className="canvas-surface">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={handleConnect}
            onNodeClick={handleNodeClick}
            fitView
            snapToGrid
            proOptions={{ hideAttribution: true }}
          >
            <MiniMap />
            <Controls />
            <Background gap={16} />
          </ReactFlow>
        </div>
        <aside className={`panel ${isConfigOpen ? "open" : "collapsed"}`}>
          <button
            type="button"
            className="panel-toggle"
            onClick={() => setConfigOpen((value) => !value)}
          >
            {isConfigOpen ? "Hide" : "Show"} Configuration
          </button>
          {isConfigOpen && (
            <div className="panel-content">
              <h2>Node Configuration</h2>
              {selectedNode ? (
                <dl>
                  <dt>Node ID</dt>
                  <dd>{selectedNode.id}</dd>
                  <dt>Label</dt>
                  <dd>{String(selectedNode.data?.label ?? selectedNode.id)}</dd>
                  <dt>Position</dt>
                  <dd>
                    {Math.round(selectedNode.position.x)},{" "}
                    {Math.round(selectedNode.position.y)}
                  </dd>
                </dl>
              ) : (
                <p>Select a node to inspect configuration.</p>
              )}

              <h2>Credential Templates</h2>
              <ul className="template-list">
                {templates.map((template) => (
                  <li key={template.slug}>
                    <div>
                      <strong>{template.name}</strong>
                      <p>{template.description}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => applyTemplate(template)}
                      aria-label={`Apply ${template.name} template`}
                    >
                      Apply
                    </button>
                  </li>
                ))}
                {templates.length === 0 && <li>No templates available.</li>}
              </ul>

              <h2>Sub-workflows</h2>
              <p>Reuse workflow components by orchestrating sub-flows.</p>
              <ul>
                <li>Approval Loop</li>
                <li>Notification Fanout</li>
              </ul>

              <h2>Execution Feed</h2>
              <ol className="execution-log">
                {executionLog.map((entry, index) => (
                  <li key={`log-${index}`}>{entry}</li>
                ))}
                {executionLog.length === 0 && <li>No executions yet.</li>}
              </ol>

              <h2>Workflow Diff</h2>
              {versionDiff ? (
                <p>{`Nodes: ${versionDiff.nodeDelta}, Edges: ${versionDiff.edgeDelta}`}</p>
              ) : (
                <p>No previous versions recorded.</p>
              )}

              <h2>Chat Preview</h2>
              <div className="chat-panel">
                <div className="chat-log" aria-live="polite">
                  {chatLog.map((message, index) => (
                    <div key={`chat-${index}`} className={`chat-message ${message.role}`}>
                      <strong>{message.role === "user" ? "You" : "Assistant"}</strong>
                      <p>{message.content}</p>
                    </div>
                  ))}
                  {chatLog.length === 0 && <p className="chat-placeholder">Start a conversation to preview the handoff experience.</p>}
                </div>
                <ChatComposer onSend={sendChatMessage} />
              </div>
            </div>
          )}
        </aside>
      </section>
    </main>
  );
}

type ChatComposerProps = {
  onSend: (message: string) => void;
};

function ChatComposer({ onSend }: ChatComposerProps) {
  const [message, setMessage] = useState("");
  return (
    <form
      className="chat-composer"
      onSubmit={(event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        onSend(message.trim());
        setMessage("");
      }}
    >
      <input
        type="text"
        value={message}
        onChange={(event) => setMessage(event.target.value)}
        placeholder="Send a test instruction"
      />
      <button type="submit">Send</button>
    </form>
  );
}
