import { useEffect, useMemo, useRef, useState } from "react";
import {
  getWorkflowTemplateDefinition,
  type Workflow,
} from "@features/workflow/data/workflow-data";
import {
  buildMermaidCacheKey,
  buildMermaidRenderId,
  forceMermaidLeftToRight,
  makeMermaidSvgTransparent,
  renderMermaidSvg,
} from "@features/workflow/lib/mermaid-renderer";

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

export const WorkflowThumbnail = ({ workflow }: WorkflowThumbnailProps) => {
  const [diagramSvg, setDiagramSvg] = useState<string | null>(null);
  const [diagramError, setDiagramError] = useState<string | null>(null);
  const [hasEnteredViewport, setHasEnteredViewport] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const latestVersion = workflow.versions?.at(-1);

  const mermaidSource = useMemo(() => {
    const templateMermaid =
      latestVersion?.templateId != null
        ? getWorkflowTemplateDefinition(
            latestVersion.templateId,
          )?.workflow.versions?.at(-1)?.mermaid
        : undefined;
    const source = templateMermaid ?? latestVersion?.mermaid;
    if (!source) {
      return null;
    }

    const trimmedSource = source.trim();
    return trimmedSource.length > 0
      ? forceMermaidLeftToRight(trimmedSource)
      : null;
  }, [latestVersion?.mermaid, latestVersion?.templateId]);

  const mermaidCacheKey = useMemo(() => {
    if (!mermaidSource) {
      return null;
    }

    return buildMermaidCacheKey({
      scope: "gallery-thumbnail",
      workflowId: workflow.id,
      versionId: latestVersion?.id ?? "latest",
      source: mermaidSource,
    });
  }, [latestVersion?.id, mermaidSource, workflow.id]);

  const renderId = useMemo(() => {
    if (!mermaidCacheKey) {
      return null;
    }

    return buildMermaidRenderId("workflow-gallery-mermaid", mermaidCacheKey);
  }, [mermaidCacheKey]);

  useEffect(() => {
    if (!mermaidSource) {
      setHasEnteredViewport(false);
      return;
    }

    const element = containerRef.current;
    if (
      !element ||
      typeof window === "undefined" ||
      typeof IntersectionObserver === "undefined"
    ) {
      setHasEnteredViewport(true);
      return;
    }

    const preloadMargin = 200;
    const rect = element.getBoundingClientRect();
    const isWithinPreloadRange =
      rect.bottom >= -preloadMargin &&
      rect.top <= window.innerHeight + preloadMargin;

    if (isWithinPreloadRange) {
      setHasEnteredViewport(true);
      return;
    }

    setHasEnteredViewport(false);
    const observer = new IntersectionObserver(
      (entries) => {
        const isIntersecting = entries.some(
          (entry) => entry.isIntersecting || entry.intersectionRatio > 0,
        );

        if (isIntersecting) {
          setHasEnteredViewport(true);
          observer.disconnect();
        }
      },
      { rootMargin: `${preloadMargin}px 0px` },
    );

    observer.observe(element);
    return () => {
      observer.disconnect();
    };
  }, [mermaidCacheKey, mermaidSource]);

  useEffect(() => {
    if (
      !mermaidSource ||
      !renderId ||
      !mermaidCacheKey ||
      !hasEnteredViewport
    ) {
      if (!mermaidSource) {
        setDiagramSvg(null);
        setDiagramError(null);
      }
      return;
    }

    setDiagramSvg(null);
    setDiagramError(null);

    let isMounted = true;

    const renderMermaidThumbnail = async () => {
      try {
        const svg = await renderMermaidSvg({
          source: mermaidSource,
          cacheKey: mermaidCacheKey,
          renderId,
          transformSvg: makeMermaidSvgTransparent,
        });
        if (!isMounted) {
          return;
        }
        setDiagramSvg(svg);
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
  }, [hasEnteredViewport, mermaidCacheKey, mermaidSource, renderId]);

  const showMermaidThumbnail = Boolean(
    mermaidSource && hasEnteredViewport && diagramSvg && !diagramError,
  );
  const showLoadingThumbnail = Boolean(
    mermaidSource && hasEnteredViewport && !diagramSvg && !diagramError,
  );
  const showFallbackThumbnail = Boolean(
    !mermaidSource || diagramError || !hasEnteredViewport,
  );

  return (
    <div
      ref={containerRef}
      className="relative h-24 w-full overflow-hidden rounded-md bg-muted/30"
    >
      {showMermaidThumbnail ? (
        <div
          className="workflow-thumbnail-mermaid absolute inset-0 flex items-center justify-center p-1 [&_svg]:block [&_svg]:max-h-full [&_svg]:max-w-full [&_svg]:!h-auto [&_svg]:!w-auto"
          dangerouslySetInnerHTML={{ __html: diagramSvg }}
        />
      ) : null}

      {showLoadingThumbnail ? (
        <div
          className="workflow-thumbnail-loading absolute inset-0 animate-pulse bg-muted/40"
          aria-hidden="true"
        />
      ) : null}

      {showFallbackThumbnail ? (
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
      ) : null}
    </div>
  );
};
