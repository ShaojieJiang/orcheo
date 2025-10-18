import { FormEvent, useEffect, useMemo, useState } from "react";
import "./app.css";

type CredentialTemplate = {
  id: string;
  name: string;
  provider: string;
  scopes: string[];
  description: string | null;
  kind: string;
  issuance_policy: {
    require_refresh_token: boolean;
    rotation_period_days: number | null;
    expiry_threshold_minutes: number;
  };
};

type GovernanceAlert = {
  id: string;
  kind: string;
  severity: string;
  message: string;
  credential_id: string | null;
  template_id: string | null;
  is_acknowledged: boolean;
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

function formatScopes(scopes: string[]): string {
  return scopes.join(", ") || "(none)";
}

export function App() {
  const [activeView, setActiveView] = useState<"templates" | "issue" | "alerts">(
    "templates",
  );
  const [templates, setTemplates] = useState<CredentialTemplate[]>([]);
  const [alerts, setAlerts] = useState<GovernanceAlert[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [formState, setFormState] = useState({
    name: "",
    provider: "",
    scopes: "",
    description: "",
    requireRefresh: false,
  });
  const [issuanceState, setIssuanceState] = useState({
    templateId: "",
    secret: "",
    name: "",
  });

  useEffect(() => {
    let cancelled = false;
    async function loadInitial() {
      try {
        const [templatePayload, alertPayload] = await Promise.all([
          apiRequest<CredentialTemplate[]>("/credentials/templates").catch(
            () => [],
          ),
          apiRequest<GovernanceAlert[]>("/credentials/governance-alerts").catch(
            () => [],
          ),
        ]);
        if (!cancelled) {
          setTemplates(templatePayload);
          setAlerts(alertPayload);
          if (templatePayload.length > 0) {
            setIssuanceState((state) => ({
              ...state,
              templateId: state.templateId || templatePayload[0].id,
            }));
          }
        }
      } catch (requestError) {
        if (!cancelled) {
          setError((requestError as Error).message);
        }
      }
    }
    void loadInitial();
    return () => {
      cancelled = true;
    };
  }, []);

  const sortedTemplates = useMemo(
    () =>
      [...templates].sort((a, b) => a.name.localeCompare(b.name)),
    [templates],
  );

  async function handleTemplateSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setStatusMessage(null);
    try {
      const payload = {
        name: formState.name.trim(),
        provider: formState.provider.trim(),
        scopes: formState.scopes
          .split(",")
          .map((scope) => scope.trim())
          .filter(Boolean),
        description: formState.description.trim() || null,
        kind: "secret",
        issuance_policy: {
          require_refresh_token: formState.requireRefresh,
          rotation_period_days: null,
          expiry_threshold_minutes: 60,
        },
        actor: "canvas-user",
      };
      const template = await apiRequest<CredentialTemplate>(
        "/credentials/templates",
        {
          method: "POST",
          body: JSON.stringify(payload),
        },
      );
      setTemplates((current) => [...current, template]);
      setFormState({
        name: "",
        provider: "",
        scopes: "",
        description: "",
        requireRefresh: false,
      });
      setStatusMessage(`Template “${template.name}” created.`);
      setIssuanceState((state) => ({
        ...state,
        templateId: state.templateId || template.id,
      }));
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleIssuanceSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setStatusMessage(null);
    try {
      const payload = {
        template_id: issuanceState.templateId,
        secret: issuanceState.secret,
        name: issuanceState.name.trim() || null,
        actor: "canvas-user",
      };
      const issued = await apiRequest<{ name: string }>(
        `/credentials/templates/${issuanceState.templateId}/issue`,
        {
          method: "POST",
          body: JSON.stringify(payload),
        },
      );
      setStatusMessage(`Credential “${issued.name}” issued.`);
      setIssuanceState((state) => ({ ...state, secret: "", name: "" }));
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleAcknowledge(alertId: string) {
    try {
      const updated = await apiRequest<GovernanceAlert>(
        `/credentials/governance-alerts/${alertId}/acknowledge`,
        {
          method: "POST",
          body: JSON.stringify({ actor: "canvas-user" }),
        },
      );
      setAlerts((current) =>
        current.map((alert) => (alert.id === alertId ? updated : alert)),
      );
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  }

  return (
    <main className="app">
      <header className="app__header">
        <h1>Credential Templates &amp; Governance</h1>
        <p>
          Manage reusable credential blueprints, mint secrets on demand, and
          review governance alerts emitted by the backend.
        </p>
        <nav className="app__nav">
          <button
            type="button"
            className={activeView === "templates" ? "active" : ""}
            onClick={() => setActiveView("templates")}
          >
            Templates
          </button>
          <button
            type="button"
            className={activeView === "issue" ? "active" : ""}
            onClick={() => setActiveView("issue")}
            disabled={templates.length === 0}
          >
            Issue Credential
          </button>
          <button
            type="button"
            className={activeView === "alerts" ? "active" : ""}
            onClick={() => setActiveView("alerts")}
          >
            Governance Alerts
          </button>
        </nav>
        {statusMessage && <div className="app__status">{statusMessage}</div>}
        {error && <div className="app__error">{error}</div>}
      </header>

      <section className="app__content">
        {activeView === "templates" && (
          <div className="panel">
            <h2>Registered Templates</h2>
            {sortedTemplates.length === 0 ? (
              <p>No templates have been created yet.</p>
            ) : (
              <ul className="template-list">
                {sortedTemplates.map((template) => (
                  <li key={template.id}>
                    <div className="template-list__header">
                      <strong>{template.name}</strong>
                      <span className="template-kind">{template.kind}</span>
                    </div>
                    <div className="template-list__meta">
                      <span>Provider: {template.provider}</span>
                      <span>Scopes: {formatScopes(template.scopes)}</span>
                    </div>
                    {template.description && (
                      <p className="template-list__description">
                        {template.description}
                      </p>
                    )}
                    {template.issuance_policy.require_refresh_token && (
                      <p className="template-list__policy">
                        Requires refresh tokens for issued credentials.
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}

            <form className="panel__form" onSubmit={handleTemplateSubmit}>
              <h3>Create template</h3>
              <label>
                Name
                <input
                  value={formState.name}
                  onChange={(event) =>
                    setFormState((state) => ({
                      ...state,
                      name: event.target.value,
                    }))
                  }
                  required
                />
              </label>
              <label>
                Provider
                <input
                  value={formState.provider}
                  onChange={(event) =>
                    setFormState((state) => ({
                      ...state,
                      provider: event.target.value,
                    }))
                  }
                  required
                />
              </label>
              <label>
                Scopes (comma separated)
                <input
                  value={formState.scopes}
                  onChange={(event) =>
                    setFormState((state) => ({
                      ...state,
                      scopes: event.target.value,
                    }))
                  }
                />
              </label>
              <label>
                Description
                <textarea
                  value={formState.description}
                  onChange={(event) =>
                    setFormState((state) => ({
                      ...state,
                      description: event.target.value,
                    }))
                  }
                />
              </label>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={formState.requireRefresh}
                  onChange={(event) =>
                    setFormState((state) => ({
                      ...state,
                      requireRefresh: event.target.checked,
                    }))
                  }
                />
                Require refresh token
              </label>
              <button type="submit" disabled={loading}>
                Save template
              </button>
            </form>
          </div>
        )}

        {activeView === "issue" && (
          <div className="panel">
            <h2>Issue credential</h2>
            {templates.length === 0 ? (
              <p>Create a template before issuing credentials.</p>
            ) : (
              <form className="panel__form" onSubmit={handleIssuanceSubmit}>
                <label>
                  Template
                  <select
                    value={issuanceState.templateId}
                    onChange={(event) =>
                      setIssuanceState((state) => ({
                        ...state,
                        templateId: event.target.value,
                      }))
                    }
                  >
                    {sortedTemplates.map((template) => (
                      <option key={template.id} value={template.id}>
                        {template.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Credential name (optional)
                  <input
                    value={issuanceState.name}
                    onChange={(event) =>
                      setIssuanceState((state) => ({
                        ...state,
                        name: event.target.value,
                      }))
                    }
                  />
                </label>
                <label>
                  Secret
                  <input
                    type="password"
                    value={issuanceState.secret}
                    onChange={(event) =>
                      setIssuanceState((state) => ({
                        ...state,
                        secret: event.target.value,
                      }))
                    }
                    required
                  />
                </label>
                <button type="submit" disabled={loading || !issuanceState.templateId}>
                  Issue credential
                </button>
              </form>
            )}
          </div>
        )}

        {activeView === "alerts" && (
          <div className="panel">
            <h2>Governance alerts</h2>
            {alerts.length === 0 ? (
              <p>No governance alerts have been recorded.</p>
            ) : (
              <ul className="alert-list">
                {alerts.map((alert) => (
                  <li key={alert.id}>
                    <div className={`alert badge-${alert.severity.toLowerCase()}`}>
                      <div className="alert__header">
                        <strong>{alert.kind}</strong>
                        {!alert.is_acknowledged && (
                          <button
                            type="button"
                            onClick={() => void handleAcknowledge(alert.id)}
                          >
                            Acknowledge
                          </button>
                        )}
                      </div>
                      <p>{alert.message}</p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
