import { useEffect, useMemo, useState } from "react";
import mermaid from "mermaid";
import { type Workflow } from "@features/workflow/data/workflow-data";

const NODE_COLORS: Record<string, string> = {
  trigger: "#f59e0b",
  api: "#3b82f6",
  function: "#8b5cf6",
  data: "#10b981",
  ai: "#6366f1",
  python: "#f97316",
};

interface WorkflowThumbnailProps {
  workflow: Workflow;
}

interface WorkflowVersionLike {
  id: string;
  mermaid?: string | null;
}

interface WorkflowWithVersions extends Workflow {
  versions?: WorkflowVersionLike[];
}

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

export const WorkflowThumbnail = ({ workflow }: WorkflowThumbnailProps) => {
  const [diagramSvg, setDiagramSvg] = useState<string | null>(null);
  const [diagramError, setDiagramError] = useState<string | null>(null);

  const latestVersion = (workflow as WorkflowWithVersions).versions?.at(-1);

  const mermaidSource = useMemo(() => {
    const source = latestVersion?.mermaid;
    if (!source) {
      return null;
    }

    const trimmedSource = source.trim();
    return trimmedSource.length > 0 ? trimmedSource : null;
  }, [latestVersion?.mermaid]);

  const renderId = useMemo(() => {
    const workflowId = sanitizeMermaidIdPart(workflow.id);
    const versionId = sanitizeMermaidIdPart(latestVersion?.id ?? "latest");
    return `workflow-gallery-mermaid-${workflowId}-${versionId}`;
  }, [latestVersion?.id, workflow.id]);

  useEffect(() => {
    if (!mermaidSource) {
      setDiagramSvg(null);
      setDiagramError(null);
      return;
    }

    let isMounted = true;

    const renderMermaidThumbnail = async () => {
      try {
        ensureMermaidInitialized();
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

    void renderMermaidThumbnail();

    return () => {
      isMounted = false;
    };
  }, [mermaidSource, renderId]);

  const showMermaidThumbnail = Boolean(
    mermaidSource && diagramSvg && !diagramError,
  );

  return (
    <div className="relative h-24 w-full overflow-hidden rounded-md bg-muted/30">
      {showMermaidThumbnail ? (
        <div
          className="workflow-thumbnail-mermaid absolute inset-0 p-1 [&_svg]:h-full [&_svg]:w-full [&_svg]:max-h-full [&_svg]:max-w-full"
          dangerouslySetInnerHTML={{ __html: diagramSvg }}
        />
      ) : (
        <svg
          width="100%"
          height="100%"
          viewBox="0 0 200 100"
          className="workflow-thumbnail-fallback absolute inset-0"
        >
          {workflow.nodes.slice(0, 5).map((node, index) => {
            const x = 30 + (index % 3) * 70;
            const y = 30 + Math.floor(index / 3) * 40;
            const color = NODE_COLORS[node.type] ?? "#99a1b3";

            return (
              <g key={node.id}>
                <rect
                  x={x - 15}
                  y={y - 10}
                  width={30}
                  height={20}
                  rx={4}
                  fill={color}
                  fillOpacity={0.3}
                  stroke={color}
                  strokeWidth={1}
                />
              </g>
            );
          })}

          {workflow.edges.slice(0, 4).map((edge) => {
            const sourceIndex = workflow.nodes.findIndex(
              (node) => node.id === edge.source,
            );
            const targetIndex = workflow.nodes.findIndex(
              (node) => node.id === edge.target,
            );

            if (
              sourceIndex < 0 ||
              targetIndex < 0 ||
              sourceIndex >= 5 ||
              targetIndex >= 5
            ) {
              return null;
            }

            const sourceX = 30 + (sourceIndex % 3) * 70 + 15;
            const sourceY = 30 + Math.floor(sourceIndex / 3) * 40;
            const targetX = 30 + (targetIndex % 3) * 70 - 15;
            const targetY = 30 + Math.floor(targetIndex / 3) * 40;

            return (
              <path
                key={edge.id}
                d={`M${sourceX},${sourceY} C${sourceX + 20},${sourceY} ${targetX - 20},${targetY} ${targetX},${targetY}`}
                stroke="#99a1b3"
                strokeWidth={1}
                fill="none"
              />
            );
          })}
        </svg>
      )}
    </div>
  );
};
