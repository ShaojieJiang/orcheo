import { useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent } from "react";
import "./app.css";

type CanvasNode = {
  id: string;
  type: string;
  label: string;
  x: number;
  y: number;
  group?: string;
  config: Record<string, unknown>;
};

type WorkflowTemplate = {
  name: string;
  description: string;
  nodes: CanvasNode[];
};

type CredentialTemplate = {
  provider: string;
  name: string;
  kind: string;
  governance_window_hours: number;
  scopes: string[];
  fields: { key: string; label: string; secret: boolean; required: boolean }[];
};

type CredentialAlert = { id: string; message: string };

type CredentialTemplateResponse = CredentialTemplate & { alerts?: string[] };

const NODE_CATALOG: CanvasNode[] = [
  {
    id: "trigger-webhook",
    type: "trigger",
    label: "Webhook Trigger",
    x: 0,
    y: 0,
    config: { description: "Receives inbound HTTP events." },
  },
  {
    id: "trigger-cron",
    type: "trigger",
    label: "Cron Trigger",
    x: 0,
    y: 0,
    config: { description: "Schedules runs on a recurring cadence." },
  },
  {
    id: "trigger-http-poll",
    type: "trigger",
    label: "HTTP Polling",
    x: 0,
    y: 0,
    config: { description: "Polls an HTTP endpoint for changes." },
  },
  {
    id: "ai-openai",
    type: "ai",
    label: "OpenAI Chat",
    x: 0,
    y: 0,
    config: { model: "gpt-4o-mini" },
  },
  {
    id: "ai-anthropic",
    type: "ai",
    label: "Anthropic Chat",
    x: 0,
    y: 0,
    config: { model: "claude-3-sonnet" },
  },
  {
    id: "utility-guardrails",
    type: "utility",
    label: "Guardrails",
    x: 0,
    y: 0,
    config: { rules: ["PromptLength", "Score"] },
  },
  {
    id: "communication-email",
    type: "communication",
    label: "Email Notification",
    x: 0,
    y: 0,
    config: { to: ["team@example.com"] },
  },
  {
    id: "communication-discord",
    type: "communication",
    label: "Discord Message",
    x: 0,
    y: 0,
    config: { channel: "alerts" },
  },
  {
    id: "logic-set-variable",
    type: "logic",
    label: "Set Variable",
    x: 0,
    y: 0,
    config: { key: "result" },
  },
  {
    id: "logic-merge",
    type: "logic",
    label: "Merge Data",
    x: 0,
    y: 0,
    config: { sources: ["ai"] },
  },
];

const WORKFLOW_TEMPLATES: WorkflowTemplate[] = [
  {
    name: "Daily Digest",
    description: "Webhook trigger fan-out to AI summarisation and email notification.",
    nodes: [
      {
        id: "digest-trigger",
        type: "trigger",
        label: "Cron Trigger",
        x: 80,
        y: 60,
        config: { expression: "0 8 * * *" },
      },
      {
        id: "digest-fetch",
        type: "data",
        label: "HTTP Request",
        x: 320,
        y: 40,
        config: { url: "https://example.com/feed" },
      },
      {
        id: "digest-ai",
        type: "ai",
        label: "OpenAI Chat",
        x: 520,
        y: 120,
        config: { prompt: "Summarise the feed" },
      },
      {
        id: "digest-email",
        type: "communication",
        label: "Email Notification",
        x: 760,
        y: 100,
        config: { to: ["team@example.com"], subject: "Daily Digest" },
      },
    ],
  },
  {
    name: "Incident Response",
    description: "Webhook trigger with guardrails and Discord notification pipeline.",
    nodes: [
      {
        id: "incident-webhook",
        type: "trigger",
        label: "Webhook Trigger",
        x: 120,
        y: 180,
        config: { secret: "shared-secret" },
      },
      {
        id: "incident-guardrails",
        type: "utility",
        label: "Guardrails",
        x: 380,
        y: 200,
        config: { rules: ["PromptLength", "Score"] },
      },
      {
        id: "incident-discord",
        type: "communication",
        label: "Discord Message",
        x: 640,
        y: 220,
        config: { channel: "incidents" },
      },
    ],
  },
];

const LOCAL_STORAGE_KEY = "orcheo-canvas-workflow";

export function App() {
  const [nodes, setNodes] = useState<CanvasNode[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const panStartRef = useRef<{ x: number; y: number } | null>(null);
  const [undoStack, setUndoStack] = useState<CanvasNode[][]>([]);
  const [redoStack, setRedoStack] = useState<CanvasNode[][]>([]);
  const [savedVersions, setSavedVersions] = useState<
    { id: string; savedAt: string; nodes: CanvasNode[] }[]
  >([]);
  const [importJson, setImportJson] = useState("");
  const [shareLink, setShareLink] = useState("");
  const [credentialTemplates, setCredentialTemplates] = useState<CredentialTemplate[]>([]);
  const [credentialAlerts, setCredentialAlerts] = useState<CredentialAlert[]>([]);
  const [workflowIdForHealth, setWorkflowIdForHealth] = useState("");
  const [wsMessages, setWsMessages] = useState<string[]>([]);
  const [wsStatus, setWsStatus] = useState("disconnected");
  const websocketRef = useRef<WebSocket | null>(null);
  const [chatInput, setChatInput] = useState("");
  const [chatTranscript, setChatTranscript] = useState<
    { role: "user" | "system"; content: string }[]
  >([]);
  const [groupName, setGroupName] = useState("");
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedNodeId) ?? null,
    [nodes, selectedNodeId],
  );

  useEffect(() => {
    const stored = window.localStorage.getItem(LOCAL_STORAGE_KEY);
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as CanvasNode[];
        setNodes(parsed);
      } catch (error) {
        console.error("Failed to parse stored workflow", error);
      }
    }
  }, []);

  useEffect(() => {
    fetch("/api/credentials/templates")
      .then(async (response) => {
        if (!response.ok) {
          throw new Error("Failed to load credential templates");
        }
        return (await response.json()) as CredentialTemplateResponse[];
      })
      .then((templates) => setCredentialTemplates(templates))
      .catch((error) => {
        console.warn(error);
      });
  }, []);

  const updateNodes = (updater: (current: CanvasNode[]) => CanvasNode[]) => {
    setNodes((current) => {
      const next = updater(current);
      setUndoStack((history) => [...history, current.map((node) => ({ ...node }))]);
      setRedoStack([]);
      return next;
    });
  };

  const addNode = (nodeTemplate: CanvasNode) => {
    updateNodes((current) => [
      ...current,
      {
        ...nodeTemplate,
        id: `${nodeTemplate.id}-${Date.now()}`,
        x: 100 + current.length * 40,
        y: 120 + current.length * 30,
      },
    ]);
  };

  const duplicateNode = () => {
    if (!selectedNode) return;
    addNode({ ...selectedNode, id: selectedNode.type });
  };

  const deleteNode = () => {
    if (!selectedNode) return;
    updateNodes((current) => current.filter((node) => node.id !== selectedNode.id));
    setSelectedNodeId(null);
  };

  const undo = () => {
    setUndoStack((history) => {
      if (!history.length) return history;
      const previous = history[history.length - 1];
      setRedoStack((stack) => [nodes.map((node) => ({ ...node })), ...stack]);
      setNodes(previous.map((node) => ({ ...node })));
      return history.slice(0, -1);
    });
  };

  const redo = () => {
    setRedoStack((stack) => {
      if (!stack.length) return stack;
      const [next, ...rest] = stack;
      setUndoStack((history) => [...history, nodes.map((node) => ({ ...node }))]);
      setNodes(next.map((node) => ({ ...node })));
      return rest;
    });
  };

  const saveWorkflow = () => {
    window.localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(nodes));
    setSavedVersions((versions) => [
      { id: `v${versions.length + 1}`, savedAt: new Date().toISOString(), nodes },
      ...versions,
    ]);
  };

  const loadWorkflow = () => {
    const stored = window.localStorage.getItem(LOCAL_STORAGE_KEY);
    if (!stored) return;
    try {
      const parsed = JSON.parse(stored) as CanvasNode[];
      setNodes(parsed);
    } catch (error) {
      console.error("Failed to load workflow", error);
    }
  };

  const exportWorkflow = () => {
    const json = JSON.stringify(nodes, null, 2);
    setImportJson(json);
    setShareLink(window.btoa(json));
  };

  const importWorkflow = () => {
    try {
      const parsed = JSON.parse(importJson) as CanvasNode[];
      setNodes(parsed);
    } catch (error) {
      console.error("Failed to import workflow", error);
    }
  };

  const handleTemplateLoad = (template: WorkflowTemplate) => {
    setNodes(template.nodes.map((node) => ({ ...node })));
    setSelectedNodeId(null);
  };

  const assignGroup = () => {
    if (!selectedNode || !groupName.trim()) return;
    updateNodes((current) =>
      current.map((node) =>
        node.id === selectedNode.id ? { ...node, group: groupName.trim() } : node,
      ),
    );
    setGroupName("");
  };

  const groups = useMemo(() => {
    const mapping: Record<string, CanvasNode[]> = {};
    nodes.forEach((node) => {
      if (!node.group) return;
      if (!mapping[node.group]) mapping[node.group] = [];
      mapping[node.group].push(node);
    });
    return mapping;
  }, [nodes]);

  const filteredCatalog = useMemo(() => {
    if (!searchQuery.trim()) return NODE_CATALOG;
    return NODE_CATALOG.filter((node) =>
      node.label.toLowerCase().includes(searchQuery.toLowerCase()),
    );
  }, [searchQuery]);

  const handleCanvasMouseDown = (event: MouseEvent<HTMLDivElement>) => {
    panStartRef.current = { x: event.clientX - pan.x, y: event.clientY - pan.y };
  };

  const handleCanvasMouseMove = (event: MouseEvent<HTMLDivElement>) => {
    if (!panStartRef.current) return;
    setPan({ x: event.clientX - panStartRef.current.x, y: event.clientY - panStartRef.current.y });
  };

  const handleCanvasMouseUp = () => {
    panStartRef.current = null;
  };

  const applyZoom = (delta: number) => {
    setZoom((value) => Math.min(2, Math.max(0.5, value + delta)));
  };

  const connectWebsocket = () => {
    if (!workflowIdForHealth.trim()) return;
    const socket = new WebSocket(
      `${window.location.origin.replace("http", "ws")}/ws/workflow/${workflowIdForHealth}`,
    );
    socket.onopen = () => setWsStatus("connected");
    socket.onclose = () => setWsStatus("disconnected");
    socket.onmessage = (event) => {
      setWsMessages((messages) => [...messages, event.data]);
    };
    websocketRef.current = socket;
  };

  const disconnectWebsocket = () => {
    websocketRef.current?.close();
    websocketRef.current = null;
  };

  const runWorkflowOverSocket = () => {
    if (!websocketRef.current) return;
    websocketRef.current.send(
      JSON.stringify({
        type: "run_workflow",
        execution_id: `exec-${Date.now()}`,
        graph_config: { nodes },
        inputs: {},
      }),
    );
  };

  const sendChatMessage = () => {
    if (!chatInput.trim()) return;
    setChatTranscript((messages) => [...messages, { role: "user", content: chatInput }]);
    if (websocketRef.current) {
      websocketRef.current.send(
        JSON.stringify({ type: "chat_message", message: chatInput, at: Date.now() }),
      );
    } else {
      setChatTranscript((messages) => [
        ...messages,
        { role: "system", content: "(offline) Message recorded for later." },
      ]);
    }
    setChatInput("");
  };

  const issueCredential = (template: CredentialTemplate) => {
    fetch(`/api/credentials/templates/${template.provider}/issue`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        actor: "designer",
        secret: "placeholder-secret",
        workflow_id: workflowIdForHealth || undefined,
      }),
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error("Failed to issue credential");
        }
        return (await response.json()) as { credential_id: string; alerts: string[] };
      })
      .then((result) => {
        setCredentialAlerts((alerts) => [
          { id: result.credential_id, message: `Credential issued (${result.credential_id})` },
          ...result.alerts.map((message, index) => ({
            id: `${result.credential_id}-${index}`,
            message,
          })),
          ...alerts,
        ]);
      })
      .catch((error) => {
        setCredentialAlerts((alerts) => [
          {
            id:
              typeof crypto !== "undefined" && "randomUUID" in crypto
                ? crypto.randomUUID()
                : `alert-${Date.now()}`,
            message: `Credential issue failed: ${error}`,
          },
          ...alerts,
        ]);
      });
  };

  const validateBeforePublish = () => {
    const errors: string[] = [];
    nodes.forEach((node) => {
      if (!node.label.trim()) {
        errors.push(`${node.id} is missing a label`);
      }
      if (!node.type.trim()) {
        errors.push(`${node.id} is missing a type`);
      }
    });
    setValidationErrors(errors);
    if (!errors.length) {
      window.alert("Workflow ready for publication!");
    }
  };

  const computeVersionDiff = (base: CanvasNode[], target: CanvasNode[]) => {
    const baseIds = new Set(base.map((node) => node.id));
    const targetIds = new Set(target.map((node) => node.id));
    const added = [...targetIds].filter((id) => !baseIds.has(id));
    const removed = [...baseIds].filter((id) => !targetIds.has(id));
    const changed = target
      .filter((node) => baseIds.has(node.id))
      .filter((node) => {
        const previous = base.find((item) => item.id === node.id)!;
        return JSON.stringify(previous) !== JSON.stringify(node);
      })
      .map((node) => node.id);
    return { added, removed, changed };
  };

  return (
    <main className="layout">
      <aside className="sidebar">
        <h1>Orcheo Canvas</h1>
        <div className="panel">
          <h2>Node Catalog</h2>
          <input
            aria-label="Search nodes"
            placeholder="Search nodes"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
          />
          <ul className="catalog">
            {filteredCatalog.map((node) => (
              <li key={node.id}>
                <button type="button" onClick={() => addNode(node)}>
                  {node.label}
                </button>
              </li>
            ))}
          </ul>
          <div className="toolbar">
            <button type="button" onClick={undo} disabled={!undoStack.length}>
              Undo
            </button>
            <button type="button" onClick={redo} disabled={!redoStack.length}>
              Redo
            </button>
            <button type="button" onClick={() => applyZoom(0.1)}>
              Zoom In
            </button>
            <button type="button" onClick={() => applyZoom(-0.1)}>
              Zoom Out
            </button>
          </div>
        </div>
        <div className="panel">
          <h2>Workflow Templates</h2>
          <ul className="catalog">
            {WORKFLOW_TEMPLATES.map((template) => (
              <li key={template.name}>
                <button type="button" onClick={() => handleTemplateLoad(template)}>
                  {template.name}
                </button>
                <p>{template.description}</p>
              </li>
            ))}
          </ul>
        </div>
        <div className="panel">
          <h2>Credential Templates</h2>
          <p className="hint">Select a workflow before issuing credentials to bind health checks.</p>
          <ul className="catalog">
            {credentialTemplates.map((template) => (
              <li key={template.provider}>
                <div className="template-row">
                  <strong>{template.name}</strong>
                  <span>{template.provider}</span>
                  <button type="button" onClick={() => issueCredential(template)}>
                    Issue
                  </button>
                </div>
                <p>Scopes: {template.scopes.join(", ")}</p>
              </li>
            ))}
          </ul>
          {credentialAlerts.slice(0, 4).map((alert) => (
            <p key={alert.id} className="alert">
              {alert.message}
            </p>
          ))}
        </div>
      </aside>

      <section
        className="canvas"
        onMouseDown={handleCanvasMouseDown}
        onMouseMove={handleCanvasMouseMove}
        onMouseUp={handleCanvasMouseUp}
        onMouseLeave={handleCanvasMouseUp}
      >
        <div
          className="canvas-inner"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
          aria-label="Workflow canvas"
        >
          {nodes.map((node) => (
            <button
              type="button"
              key={node.id}
              className={`canvas-node ${selectedNodeId === node.id ? "selected" : ""}`}
              style={{ left: node.x, top: node.y }}
              onClick={() => setSelectedNodeId(node.id)}
            >
              <span className="node-label">{node.label}</span>
              <span className="node-type">{node.type}</span>
              {node.group ? <span className="node-group">{node.group}</span> : null}
            </button>
          ))}
        </div>
        <div className="minimap" aria-label="Workflow minimap">
          {nodes.map((node) => (
            <div
              key={`mini-${node.id}`}
              className="minimap-node"
              style={{ left: node.x / 10, top: node.y / 10 }}
            />
          ))}
        </div>
      </section>

      <aside className="sidebar">
        <div className="panel">
          <h2>Selected Node</h2>
          {selectedNode ? (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                if (!selectedNode) return;
                updateNodes((current) =>
                  current.map((node) =>
                    node.id === selectedNode.id
                      ? {
                          ...node,
                          label: (event.currentTarget.elements.namedItem("label") as HTMLInputElement).value,
                          type: (event.currentTarget.elements.namedItem("type") as HTMLInputElement).value,
                        }
                      : node,
                  ),
                );
              }}
            >
              <label htmlFor="node-label">Label</label>
              <input
                id="node-label"
                name="label"
                defaultValue={selectedNode.label}
                required
              />
              <label htmlFor="node-type">Type</label>
              <input id="node-type" name="type" defaultValue={selectedNode.type} required />
              <div className="toolbar">
                <button type="submit">Update</button>
                <button type="button" onClick={duplicateNode}>
                  Duplicate
                </button>
                <button type="button" onClick={deleteNode}>
                  Delete
                </button>
              </div>
              <div className="grouping">
                <input
                  placeholder="Group name"
                  value={groupName}
                  onChange={(event) => setGroupName(event.target.value)}
                />
                <button type="button" onClick={assignGroup}>
                  Assign Group
                </button>
              </div>
            </form>
          ) : (
            <p>Select a node to configure properties.</p>
          )}
        </div>
        <div className="panel">
          <h2>Persistence</h2>
          <div className="toolbar">
            <button type="button" onClick={saveWorkflow}>
              Save
            </button>
            <button type="button" onClick={loadWorkflow}>
              Load
            </button>
            <button type="button" onClick={exportWorkflow}>
              Export JSON
            </button>
            <button type="button" onClick={importWorkflow}>
              Import JSON
            </button>
          </div>
          <textarea
            aria-label="Workflow JSON"
            placeholder="Workflow JSON"
            value={importJson}
            onChange={(event) => setImportJson(event.target.value)}
          />
          <label htmlFor="share-link">Shareable Export</label>
          <textarea id="share-link" readOnly value={shareLink} />
          <button
            type="button"
            onClick={() => navigator.clipboard.writeText(shareLink)}
            disabled={!shareLink}
          >
            Copy Share Link
          </button>
        </div>
        <div className="panel">
          <h2>Version Diff</h2>
          {savedVersions.length >= 2 ? (
            <VersionDiffViewer versions={savedVersions} computeDiff={computeVersionDiff} />
          ) : (
            <p>Save at least two versions to compute diffs.</p>
          )}
        </div>
        <div className="panel">
          <h2>Observability</h2>
          <input
            placeholder="Workflow ID"
            value={workflowIdForHealth}
            onChange={(event) => setWorkflowIdForHealth(event.target.value)}
          />
          <div className="toolbar">
            <button type="button" onClick={connectWebsocket} disabled={wsStatus === "connected"}>
              Connect
            </button>
            <button type="button" onClick={disconnectWebsocket}>
              Disconnect
            </button>
            <button type="button" onClick={runWorkflowOverSocket} disabled={wsStatus !== "connected"}>
              Run Workflow
            </button>
          </div>
          <p>Status: {wsStatus}</p>
          <div className="ws-log" aria-live="polite">
            {wsMessages.slice(-6).map((message, index) => (
              <pre key={`ws-${index}`}>{message}</pre>
            ))}
          </div>
        </div>
        <div className="panel">
          <h2>Chat Console</h2>
          <div className="chat-log">
            {chatTranscript.map((entry, index) => (
              <p key={`chat-${index}`} className={entry.role}>
                <strong>{entry.role === "user" ? "You" : "System"}:</strong> {entry.content}
              </p>
            ))}
          </div>
          <div className="chat-input">
            <input
              placeholder="Send a message"
              value={chatInput}
              onChange={(event) => setChatInput(event.target.value)}
            />
            <button type="button" onClick={sendChatMessage}>
              Send
            </button>
          </div>
        </div>
        <div className="panel">
          <h2>Publish Workflow</h2>
          <button type="button" onClick={validateBeforePublish}>
            Publish
          </button>
          {validationErrors.map((error) => (
            <p key={error} className="alert">
              {error}
            </p>
          ))}
        </div>
        <div className="panel">
          <h2>Groups</h2>
          {Object.entries(groups).length ? (
            <ul>
              {Object.entries(groups).map(([name, nodes]) => (
                <li key={name}>
                  <strong>{name}</strong>
                  <span>{nodes.length} nodes</span>
                </li>
              ))}
            </ul>
          ) : (
            <p>No sub-workflows yet.</p>
          )}
        </div>
      </aside>
    </main>
  );
}

function VersionDiffViewer({
  versions,
  computeDiff,
}: {
  versions: { id: string; savedAt: string; nodes: CanvasNode[] }[];
  computeDiff: (base: CanvasNode[], target: CanvasNode[]) => {
    added: string[];
    removed: string[];
    changed: string[];
  };
}) {
  const [baseId, setBaseId] = useState(versions[0]?.id ?? "");
  const [targetId, setTargetId] = useState(versions[1]?.id ?? "");

  const base = versions.find((version) => version.id === baseId) ?? versions[0];
  const target = versions.find((version) => version.id === targetId) ?? versions[1];

  if (!base || !target) {
    return <p>Select versions to view a diff.</p>;
  }

  const diff = computeDiff(base.nodes, target.nodes);

  return (
    <div className="diff-viewer">
      <div className="diff-selectors">
        <label>
          Base
          <select value={baseId} onChange={(event) => setBaseId(event.target.value)}>
            {versions.map((version) => (
              <option key={version.id} value={version.id}>
                {version.id} – {new Date(version.savedAt).toLocaleString()}
              </option>
            ))}
          </select>
        </label>
        <label>
          Target
          <select value={targetId} onChange={(event) => setTargetId(event.target.value)}>
            {versions.map((version) => (
              <option key={version.id} value={version.id}>
                {version.id} – {new Date(version.savedAt).toLocaleString()}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="diff-results">
        <p>
          <strong>Added:</strong> {diff.added.join(", ") || "–"}
        </p>
        <p>
          <strong>Removed:</strong> {diff.removed.join(", ") || "–"}
        </p>
        <p>
          <strong>Changed:</strong> {diff.changed.join(", ") || "–"}
        </p>
      </div>
    </div>
  );
}

export default App;
