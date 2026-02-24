import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
const DEFAULT_ZOOM_PERCENT = 100;
const MIN_ZOOM_PERCENT = 40;
const MAX_ZOOM_PERCENT = 300;
const ZOOM_STEP_PERCENT = 20;

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

const clampZoom = (zoom: number) =>
  Math.min(MAX_ZOOM_PERCENT, Math.max(MIN_ZOOM_PERCENT, zoom));

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
  const [zoomPercent, setZoomPercent] = useState(DEFAULT_ZOOM_PERCENT);
  const mermaidContainerRef = useRef<HTMLDivElement | null>(null);

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
        setZoomPercent(DEFAULT_ZOOM_PERCENT);
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

  const updateSvgPresentation = useCallback(() => {
    const wrapper = mermaidContainerRef.current;
    if (!wrapper) {
      return;
    }
    const svg = wrapper.querySelector("svg");
    if (!(svg instanceof SVGSVGElement)) {
      return;
    }

    svg.style.display = "block";
    svg.style.width = `${zoomPercent}%`;
    svg.style.height = "auto";
    svg.style.maxWidth = "none";
    svg.removeAttribute("width");
    svg.removeAttribute("height");
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");

    const graphGroup =
      (svg.querySelector("g.output") as SVGGElement | null) ??
      (svg.querySelector("g.root") as SVGGElement | null) ??
      (svg.querySelector("g") as SVGGElement | null);
    if (!graphGroup || typeof graphGroup.getBBox !== "function") {
      return;
    }

    try {
      const box = graphGroup.getBBox();
      if (box.width <= 0 || box.height <= 0) {
        return;
      }
      const padding = Math.max(box.width, box.height) * 0.08;
      const viewBox = [
        box.x - padding,
        box.y - padding,
        box.width + padding * 2,
        box.height + padding * 2,
      ].join(" ");
      svg.setAttribute("viewBox", viewBox);
    } catch {
      // Keep Mermaid's generated viewBox if bbox measurement is unavailable.
    }
  }, [zoomPercent]);

  useEffect(() => {
    if (!diagramSvg) {
      return;
    }
    const frame = window.requestAnimationFrame(updateSvgPresentation);
    return () => window.cancelAnimationFrame(frame);
  }, [diagramSvg, updateSvgPresentation]);

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
        <div className="min-h-0 flex flex-1 flex-col rounded-md border bg-muted/10 p-3">
          <div className="mb-2 flex items-center justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setZoomPercent((current) =>
                  clampZoom(current - ZOOM_STEP_PERCENT),
                );
              }}
              disabled={zoomPercent <= MIN_ZOOM_PERCENT}
            >
              -
            </Button>
            <span className="w-12 text-center text-xs text-muted-foreground">
              {zoomPercent}%
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setZoomPercent((current) =>
                  clampZoom(current + ZOOM_STEP_PERCENT),
                );
              }}
              disabled={zoomPercent >= MAX_ZOOM_PERCENT}
            >
              +
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setZoomPercent(DEFAULT_ZOOM_PERCENT);
              }}
              disabled={zoomPercent === DEFAULT_ZOOM_PERCENT}
            >
              Fit
            </Button>
          </div>
          <div className="min-h-0 flex-1 overflow-auto rounded-md border bg-background/70 p-4">
            <div className="flex min-h-full min-w-full items-center justify-center">
              {diagramSvg ? (
                <div
                  ref={mermaidContainerRef}
                  className="workflow-mermaid flex w-full justify-center [&_svg]:mx-auto [&_svg]:block"
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
