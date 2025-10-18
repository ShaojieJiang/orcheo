import { useState } from "react";
import { WorkflowCanvas } from "./components/WorkflowCanvas";
import { WorkflowOperations } from "./components/WorkflowOperations";
import { CredentialPanel } from "./components/CredentialPanel";
import { ExecutionPanel } from "./components/ExecutionPanel";
import { ChatPanel } from "./components/ChatPanel";
import { useWorkflowState } from "./hooks/useWorkflowState";
import "./app.css";

const NODE_TYPES = ["trigger", "ai", "action", "data", "storage", "utility"];

export function App() {
  const workflow = useWorkflowState();
  const [workflowId, setWorkflowId] = useState("demo-workflow");

  return (
    <main className="app">
      <header className="app__header">
        <div>
          <h1>Orcheo Canvas</h1>
          <p>
            Design workflows with drag-and-drop controls, manage credentials, and
            validate execution flows before publishing.
          </p>
        </div>
        <div className="app__workflow-id">
          <label>
            Workflow ID
            <input
              value={workflowId}
              onChange={(event) => setWorkflowId(event.target.value)}
            />
          </label>
        </div>
      </header>

      <section className="app__designer">
        <aside className="app__sidebar">
          <div className="sidebar__section">
            <h2>Node Library</h2>
            <div className="sidebar__buttons">
              {NODE_TYPES.map((type) => (
                <button key={type} type="button" onClick={() => workflow.addNode(type)}>
                  Add {type}
                </button>
              ))}
            </div>
          </div>
          <div className="sidebar__section">
            <h2>Editing Tools</h2>
            <div className="sidebar__buttons">
              <button type="button" onClick={workflow.undo} disabled={!workflow.canUndo}>
                Undo
              </button>
              <button type="button" onClick={workflow.redo} disabled={!workflow.canRedo}>
                Redo
              </button>
              <button type="button" onClick={workflow.duplicateSelected}>
                Duplicate
              </button>
              <button type="button" onClick={workflow.deleteSelected}>
                Delete
              </button>
            </div>
            <label className="sidebar__search">
              <span>Search nodes</span>
              <input
                value={workflow.searchTerm}
                onChange={(event) => workflow.setSearchTerm(event.target.value)}
                placeholder="Search by label or type"
              />
            </label>
          </div>
          <CredentialPanel
            credentialAssignments={workflow.credentialAssignments}
            nodes={workflow.nodes.map((node) => ({
              id: node.id,
              label: String(node.data.label ?? node.id),
              requiresCredential: Boolean(node.data.requiresCredential),
            }))}
            assignCredential={workflow.assignCredential}
          />
        </aside>
        <div className="app__canvas">
          <WorkflowCanvas
            nodes={workflow.filteredNodes}
            edges={workflow.edges}
            onNodesChange={workflow.onNodesChange}
            onEdgesChange={workflow.onEdgesChange}
            onConnect={workflow.onConnect}
            onSelectNode={workflow.selectNode}
          />
        </div>
      </section>

      <WorkflowOperations
        saveWorkflow={() => workflow.saveWorkflow("manual")}
        loadWorkflow={() => workflow.loadWorkflow("manual")}
        exportWorkflow={workflow.exportWorkflow}
        importWorkflow={workflow.importWorkflow}
        templates={workflow.templates}
        applyTemplate={workflow.applyTemplate}
        shareWorkflow={workflow.shareWorkflow}
        versions={workflow.versions}
        computeDiff={workflow.computeDiff}
        createSubWorkflow={workflow.createSubWorkflow}
        applySubWorkflow={workflow.applySubWorkflow}
        subWorkflows={workflow.subWorkflows}
        validateForPublish={workflow.validateForPublish}
      />

      <section className="app__runtime">
        <ExecutionPanel workflowId={workflowId} />
        <ChatPanel workflowId={workflowId} />
      </section>
    </main>
  );
}
