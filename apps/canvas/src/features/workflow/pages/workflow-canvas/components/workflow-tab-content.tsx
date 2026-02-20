import { useEffect, useMemo, useState } from "react";
import mermaid from "mermaid";

import { Button } from "@/design-system/ui/button";
import type {
  WorkflowRunnableConfig,
  WorkflowVersionRecord,
} from "@features/workflow/lib/workflow-storage.types";
import { WorkflowConfigSheet } from "@features/workflow/pages/workflow-canvas/components/workflow-config-sheet";

export interface WorkflowTabContentProps {
  workflowId: string | null;
  workflowName: string;
  versions: WorkflowVersionRecord[];
  isLoading: boolean;
  loadError: string | null;
  onSaveConfig: (nextConfig: WorkflowRunnableConfig | null) => Promise<void>;
}

const defaultMermaid = "flowchart TD\n  START([Start]) --> END([End])";

let mermaidInitialized = false;

const ensureMermaidInitialized = () => {
  if (mermaidInitialized) {
    return;
  }
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: "strict",
    theme: "neutral",
  });
  mermaidInitialized = true;
};

export function WorkflowTabContent({
  workflowId,
  workflowName,
  versions,
  isLoading,
  loadError,
  onSaveConfig,
}: WorkflowTabContentProps) {
  const latestVersion = versions.at(-1);
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const [diagramSvg, setDiagramSvg] = useState<string | null>(null);
  const [diagramError, setDiagramError] = useState<string | null>(null);

  const mermaidSource = useMemo(() => {
    if (!latestVersion?.mermaid || latestVersion.mermaid.trim().length === 0) {
      return null;
    }
    return latestVersion.mermaid;
  }, [latestVersion?.mermaid]);

  useEffect(() => {
    if (!mermaidSource) {
      setDiagramSvg(null);
      setDiagramError(null);
      return;
    }

    let isMounted = true;
    const renderMermaid = async () => {
      try {
        ensureMermaidInitialized();
        const renderId = `workflow-mermaid-${latestVersion?.id ?? "latest"}`;
        const result = await mermaid.render(renderId, mermaidSource);
        if (!isMounted) {
          return;
        }
        setDiagramSvg(result.svg);
        setDiagramError(null);
      } catch (error) {
        if (!isMounted) {
          return;
        }
        setDiagramSvg(null);
        setDiagramError(
          error instanceof Error ? error.message : "Unable to render diagram.",
        );
      }
    };

    void renderMermaid();

    return () => {
      isMounted = false;
    };
  }, [latestVersion?.id, mermaidSource]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-sm text-muted-foreground">
        Loading workflow visualization...
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="rounded-md border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
          Failed to load workflow: {loadError}
        </div>
      </div>
    );
  }

  const canConfigure = Boolean(workflowId);
  const latestConfig = latestVersion?.runnableConfig ?? null;

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <div className="flex items-center justify-between border-b pb-3">
        <div>
          <h2 className="text-lg font-semibold">Workflow</h2>
          <p className="text-sm text-muted-foreground">
            {workflowName}
            {latestVersion ? ` · ${latestVersion.version}` : ""}
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => setIsConfigOpen(true)}
          disabled={!canConfigure}
        >
          Config
        </Button>
      </div>

      {!latestVersion && (
        <div className="flex h-full items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground">
          Save this workflow to generate a versioned Mermaid diagram.
        </div>
      )}

      {latestVersion && !mermaidSource && (
        <div className="flex h-full items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground">
          Mermaid data is unavailable for this workflow version.
        </div>
      )}

      {latestVersion && mermaidSource && diagramError && (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
          Unable to render Mermaid diagram: {diagramError}
        </div>
      )}

      {latestVersion && mermaidSource && !diagramError && (
        <div className="min-h-0 flex-1 overflow-auto rounded-md border bg-muted/10 p-4">
          <div className="flex min-h-full min-w-full items-center justify-center">
            {diagramSvg ? (
              <div
                className="workflow-mermaid [&_svg]:mx-auto [&_svg]:block [&_svg]:h-auto [&_svg]:max-w-full"
                dangerouslySetInnerHTML={{
                  __html: diagramSvg,
                }}
              />
            ) : (
              <pre className="max-w-full overflow-auto rounded-md border bg-background p-3 text-xs text-muted-foreground">
                {defaultMermaid}
              </pre>
            )}
          </div>
        </div>
      )}

      <WorkflowConfigSheet
        open={isConfigOpen}
        onOpenChange={setIsConfigOpen}
        initialConfig={latestConfig}
        onSave={onSaveConfig}
      />
    </div>
  );
}
