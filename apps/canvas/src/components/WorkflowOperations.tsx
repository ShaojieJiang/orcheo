import { FormEvent, useState } from "react";
import { VersionDiff } from "../hooks/useWorkflowState";

type Props = {
  saveWorkflow: () => void;
  loadWorkflow: () => void;
  exportWorkflow: () => string;
  importWorkflow: (payload: string) => void;
  templates: { id: string; name: string; description: string }[];
  applyTemplate: (templateId: string) => void;
  shareWorkflow: () => string;
  versions: string[];
  computeDiff: (versionA: string, versionB: string) => VersionDiff | null;
  createSubWorkflow: (name: string) => void;
  applySubWorkflow: (subWorkflowId: string) => void;
  subWorkflows: { id: string; name: string }[];
  validateForPublish: () => string[];
};

export function WorkflowOperations({
  saveWorkflow,
  loadWorkflow,
  exportWorkflow,
  importWorkflow,
  templates,
  applyTemplate,
  shareWorkflow,
  versions,
  computeDiff,
  createSubWorkflow,
  applySubWorkflow,
  subWorkflows,
  validateForPublish,
}: Props) {
  const [importPayload, setImportPayload] = useState("");
  const [shareToken, setShareToken] = useState<string | null>(null);
  const [diff, setDiff] = useState<VersionDiff | null>(null);
  const [subWorkflowName, setSubWorkflowName] = useState("");
  const [publishIssues, setPublishIssues] = useState<string[]>([]);

  const handleImport = (event: FormEvent) => {
    event.preventDefault();
    if (!importPayload.trim()) return;
    importWorkflow(importPayload);
    setImportPayload("");
  };

  return (
    <section className="operations">
      <header>
        <h2>Workflow Operations</h2>
        <p>Save, export, and validate the workflow before publishing.</p>
      </header>
      <div className="operations__grid">
        <div>
          <h3>Persistence</h3>
          <button type="button" onClick={() => saveWorkflow()}>
            Save Snapshot
          </button>
          <button type="button" onClick={() => loadWorkflow()}>
            Load Snapshot
          </button>
        </div>
        <div>
          <h3>Import / Export</h3>
          <form onSubmit={handleImport} className="operations__import">
            <textarea
              aria-label="Workflow JSON"
              value={importPayload}
              onChange={(event) => setImportPayload(event.target.value)}
            />
            <button type="submit">Import JSON</button>
          </form>
          <button
            type="button"
            onClick={() => {
              const exported = exportWorkflow();
              navigator.clipboard?.writeText(exported).catch(() => undefined);
              alert("Workflow copied to clipboard");
            }}
          >
            Export JSON
          </button>
        </div>
        <div>
          <h3>Templates</h3>
          <ul>
            {templates.map((template) => (
              <li key={template.id}>
                <button type="button" onClick={() => applyTemplate(template.id)}>
                  {template.name}
                </button>
                <span>{template.description}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3>Share & Diff</h3>
          <button
            type="button"
            onClick={() => setShareToken(shareWorkflow())}
          >
            Generate Share Token
          </button>
          {shareToken ? (
            <code className="operations__token" data-testid="share-token">
              {shareToken}
            </code>
          ) : null}
          <div className="operations__diff">
            <label>
              Compare latest with saved versions
              <select
                onChange={(event) => {
                  const versionA = versions[0];
                  const versionB = event.target.value;
                  if (!versionA || !versionB) return;
                  setDiff(computeDiff(versionA, versionB));
                }}
              >
                <option value="">Select version</option>
                {versions.map((version) => (
                  <option key={version} value={version}>
                    {version}
                  </option>
                ))}
              </select>
            </label>
            {diff ? (
              <div className="operations__diff-result">
                <p>
                  Added: <strong>{diff.addedNodes.join(", ") || "None"}</strong>
                </p>
                <p>
                  Removed: <strong>{diff.removedNodes.join(", ") || "None"}</strong>
                </p>
              </div>
            ) : null}
          </div>
        </div>
        <div>
          <h3>Reusable Sub-workflows</h3>
          <div className="operations__subworkflow">
            <input
              placeholder="Sub-workflow name"
              value={subWorkflowName}
              onChange={(event) => setSubWorkflowName(event.target.value)}
            />
            <button
              type="button"
              onClick={() => {
                if (!subWorkflowName.trim()) return;
                createSubWorkflow(subWorkflowName);
                setSubWorkflowName("");
              }}
            >
              Save Selection
            </button>
          </div>
          <select
            onChange={(event) => {
              if (!event.target.value) return;
              applySubWorkflow(event.target.value);
            }}
          >
            <option value="">Insert saved workflow</option>
            {subWorkflows.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <h3>Publish Readiness</h3>
          <button
            type="button"
            onClick={() => setPublishIssues(validateForPublish())}
          >
            Run Validation
          </button>
          <ul className="operations__issues">
            {publishIssues.length === 0 ? (
              <li className="operations__issues--ok">All checks passed</li>
            ) : (
              publishIssues.map((issue) => <li key={issue}>{issue}</li>)
            )}
          </ul>
        </div>
      </div>
    </section>
  );
}
