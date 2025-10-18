import { useEffect, useState } from "react";
import { CredentialAssignments } from "../hooks/useWorkflowState";

type CredentialTemplate = {
  provider: string;
  display_name: string;
  description: string;
  scopes: string[];
};

const FALLBACK_TEMPLATES: CredentialTemplate[] = [
  {
    provider: "slack",
    display_name: "Slack Bot Token",
    description: "OAuth token used for notifications",
    scopes: ["chat:write"],
  },
  {
    provider: "http_basic",
    display_name: "HTTP Basic",
    description: "Username/password credential",
    scopes: ["http:request"],
  },
];

type Props = {
  credentialAssignments: CredentialAssignments;
  nodes: { id: string; label: string; requiresCredential?: boolean }[];
  assignCredential: (nodeId: string, credential: string) => void;
};

async function fetchTemplates(): Promise<CredentialTemplate[]> {
  try {
    const response = await fetch("/api/credentials/templates");
    if (!response.ok) {
      throw new Error("Failed to load templates");
    }
    const payload = (await response.json()) as {
      templates: CredentialTemplate[];
    };
    return payload.templates;
  } catch (error) {
    console.warn("Falling back to static credential templates", error);
    return FALLBACK_TEMPLATES;
  }
}

export function CredentialPanel({
  credentialAssignments,
  nodes,
  assignCredential,
}: Props) {
  const [templates, setTemplates] = useState<CredentialTemplate[]>(FALLBACK_TEMPLATES);

  useEffect(() => {
    void fetchTemplates().then(setTemplates);
  }, []);

  const actionableNodes = nodes.filter((node) => node.requiresCredential);

  return (
    <section className="credential-panel">
      <header>
        <h2>Credential Manager</h2>
        <p>Assign vault credentials to nodes that require secrets.</p>
      </header>
      <div>
        {actionableNodes.length === 0 ? (
          <p className="credential-panel__empty">No nodes require credentials.</p>
        ) : (
          actionableNodes.map((node) => (
            <div className="credential-panel__item" key={node.id}>
              <strong>{node.label}</strong>
              <select
                value={credentialAssignments[node.id] ?? ""}
                onChange={(event) => assignCredential(node.id, event.target.value)}
              >
                <option value="">Select credential</option>
                {templates.map((template) => (
                  <option key={template.provider} value={template.provider}>
                    {template.display_name}
                  </option>
                ))}
              </select>
              <small>
                {templates.find((template) => template.provider === credentialAssignments[node.id])?.description ||
                  "Assign a credential to enable execution."}
              </small>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
