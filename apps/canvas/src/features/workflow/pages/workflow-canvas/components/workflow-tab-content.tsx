import { useEffect, useMemo, useState } from "react";
import mermaid from "mermaid";
import { Controls, ReactFlow, type Node, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

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

interface MermaidSvgNodeData {
  svg: string;
  width: number;
  height: number;
}

const defaultMermaid = "flowchart TD\n  START([Start]) --> END([End])";
const DEFAULT_SVG_SIZE = { width: 960, height: 560 };
const MIN_SVG_WIDTH = 320;
const MIN_SVG_HEIGHT = 220;
const MAX_SVG_WIDTH = 2400;
const MAX_SVG_HEIGHT = 1800;

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

const sanitizeMermaidIdPart = (value: string): string =>
  value.replace(/[^a-zA-Z0-9_-]/g, "-");

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

const parseSvgDimension = (rawValue: string | undefined): number | null => {
  if (!rawValue) {
    return null;
  }

  const match = rawValue.match(/-?\d*\.?\d+/);
  if (!match) {
    return null;
  }

  const parsed = Number.parseFloat(match[0]);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
};

const resolveSvgSize = (svg: string) => {
  const viewBoxMatch = svg.match(/\bviewBox\s*=\s*"([^"]+)"/i);
  if (viewBoxMatch) {
    const values = viewBoxMatch[1]
      .trim()
      .split(/[\s,]+/)
      .map((value) => Number.parseFloat(value));

    if (
      values.length === 4 &&
      values.every((value) => Number.isFinite(value)) &&
      values[2] > 0 &&
      values[3] > 0
    ) {
      return {
        width: clamp(values[2], MIN_SVG_WIDTH, MAX_SVG_WIDTH),
        height: clamp(values[3], MIN_SVG_HEIGHT, MAX_SVG_HEIGHT),
      };
    }
  }

  const width = parseSvgDimension(svg.match(/\bwidth\s*=\s*"([^"]+)"/i)?.[1]);
  const height = parseSvgDimension(svg.match(/\bheight\s*=\s*"([^"]+)"/i)?.[1]);

  if (width && height) {
    return {
      width: clamp(width, MIN_SVG_WIDTH, MAX_SVG_WIDTH),
      height: clamp(height, MIN_SVG_HEIGHT, MAX_SVG_HEIGHT),
    };
  }

  return DEFAULT_SVG_SIZE;
};

const makeMermaidSvgTransparent = (svg: string): string => {
  const svgWithTransparentRoot = svg.replace(
    /<svg\b([^>]*)>/i,
    (match, attributes: string) => {
      const styleMatch = attributes.match(/\sstyle="([^"]*)"/i);
      if (!styleMatch) {
        return `<svg${attributes} style="background-color: transparent;">`;
      }

      const cleanedStyle = styleMatch[1]
        .split(";")
        .map((entry) => entry.trim())
        .filter(Boolean)
        .filter(
          (entry) =>
            !entry.toLowerCase().startsWith("background-color") &&
            !entry.toLowerCase().startsWith("background"),
        )
        .join("; ");
      const nextStyle = ` style="background-color: transparent${cleanedStyle ? `; ${cleanedStyle}` : ""};"`;

      return match.replace(styleMatch[0], nextStyle);
    },
  );

  return svgWithTransparentRoot
    .replace(
      /<rect\b([^>]*\bclass="[^"]*\b(background|canvas)\b[^"]*"[^>]*)\/?>/gi,
      "",
    )
    .replace(
      /<rect\b([^>]*\bid="[^"]*(background|canvas)[^"]*"[^>]*)\/?>/gi,
      "",
    );
};

const MermaidSvgNode = ({ data }: NodeProps<Node<MermaidSvgNodeData>>) => {
  const nodeData = data as MermaidSvgNodeData;

  return (
    <div className="p-1">
      <div
        className="workflow-mermaid-svg pointer-events-none [&_svg]:block [&_svg]:h-full [&_svg]:w-full [&_svg]:max-w-none"
        style={{ width: nodeData.width, height: nodeData.height }}
        dangerouslySetInnerHTML={{ __html: nodeData.svg }}
      />
    </div>
  );
};

const nodeTypes = {
  mermaidSvg: MermaidSvgNode,
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
        const workflowIdPart = sanitizeMermaidIdPart(workflowId ?? "workflow");
        const versionIdPart = sanitizeMermaidIdPart(
          latestVersion?.id ?? "latest",
        );
        const renderId = `workflow-mermaid-svg-${workflowIdPart}-${versionIdPart}`;
        const result = await mermaid.render(renderId, mermaidSource);

        if (!isMounted) {
          return;
        }

        setDiagramSvg(makeMermaidSvgTransparent(result.svg));
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
  }, [latestVersion?.id, mermaidSource, workflowId]);

  const diagramNodes = useMemo(() => {
    if (!diagramSvg) {
      return [] as Node[];
    }

    const size = resolveSvgSize(diagramSvg);

    return [
      {
        id: "mermaid-svg-root",
        type: "mermaidSvg",
        position: { x: 0, y: 0 },
        data: {
          svg: diagramSvg,
          width: size.width,
          height: size.height,
        },
        draggable: false,
        selectable: false,
      } satisfies Node,
    ];
  }, [diagramSvg]);

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
        <div className="min-h-0 flex flex-1 flex-col">
          <div className="min-h-0 flex-1 overflow-hidden">
            {diagramNodes.length > 0 ? (
              <ReactFlow
                key={`${latestVersion.id}-mermaid-svg`}
                nodes={diagramNodes}
                edges={[]}
                nodeTypes={nodeTypes}
                fitView
                minZoom={0.2}
                maxZoom={2}
                nodesDraggable={false}
                nodesConnectable={false}
                elementsSelectable={false}
                zoomOnDoubleClick={false}
                className="h-full w-full"
                proOptions={{ hideAttribution: true }}
                style={{ background: "transparent" }}
              >
                <Controls showInteractive={false} />
              </ReactFlow>
            ) : (
              <pre className="h-full overflow-auto p-3 text-xs text-muted-foreground">
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
